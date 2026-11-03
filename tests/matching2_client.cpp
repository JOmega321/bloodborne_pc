// SPDX-License-Identifier: GPL-2.0-or-later
// Calls production PS4 imports from libbbnet20 via its normal ABI 2 resolver.
// The process intentionally exits after the peer has time to complete its callback/data check.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <pthread.h>
#include <thread>
#include "bbnet20/bbnet.h"
#include "core/libraries/net/net.h"
#include "core/libraries/np/np_signaling/np_signaling.h"
#include <arpa/inet.h>
#include "core/libraries/np/np_matching2/np_matching2.h"
using namespace Libraries::Np;
using namespace Libraries::Np::NpMatching2;
static std::atomic<bool> started{false}, joined{false}, established{false};
static std::atomic<bool> sig1_ready{false};
static void sig1_cb(u32,u32,s32 event,s32 error,void*) {
 if(event==1 && error==0) {sig1_ready=true;puts("SIG1_ESTABLISHED");std::fflush(stdout);}
}
static std::atomic<u64> room{0};
static std::atomic<u16> peer_member{0};
static s32 spawn(void** out, void* (*entry)(void*), void* arg, u64, const char*) {
    auto* t = new pthread_t{}; int rc = pthread_create(t, nullptr, entry, arg); *out = t; return rc;
}
static s32 join(void* t, void** result) {int rc=pthread_join(*static_cast<pthread_t*>(t),result); delete static_cast<pthread_t*>(t);return rc;}
static void exit_thread(void* result) {pthread_exit(result);}
static int mapped(uintptr_t, u64) {return 0;}
static void context_cb(OrbisNpMatching2ContextId, OrbisNpMatching2Event event,
                       OrbisNpMatching2EventCause, int error, void*) {
    if (error) {std::printf("CONTEXT_ERROR %x\n",error);std::fflush(stdout);return;}
    if (event == ORBIS_NP_MATCHING2_CONTEXT_EVENT_STARTED) started=true;
}
static void request_cb(OrbisNpMatching2ContextId, OrbisNpMatching2RequestId,
                      OrbisNpMatching2Event event, s32 error, const void* data, void*) {
    if (error) {std::printf("REQUEST_ERROR %x\n",error);std::fflush(stdout);return;}
    if (event == ORBIS_NP_MATCHING2_REQUEST_EVENT_CREATE_JOIN_ROOM ||
        event == ORBIS_NP_MATCHING2_REQUEST_EVENT_JOIN_ROOM) {
        const auto* response=static_cast<const OrbisNpMatching2CreateJoinRoomResponse*>(data);
        room=response->roomData->roomId;joined=true;
        std::printf("ROOM %llu\n",static_cast<unsigned long long>(room.load()));std::fflush(stdout);
    }
}
static void room_cb(OrbisNpMatching2ContextId, OrbisNpMatching2RoomId, OrbisNpMatching2Event, const void*, void*) {}
static void signaling_cb(OrbisNpMatching2ContextId, OrbisNpMatching2RoomId,
                        OrbisNpMatching2RoomMemberId member, OrbisNpMatching2Event event, int error, void*) {
    std::printf("ROOM_SIGNAL %x %x\n",event,error);std::fflush(stdout);
    if(event==ORBIS_NP_MATCHING2_SIGNALING_EVENT_ESTABLISHED && error==0) {peer_member=member;established=true;}
}
static void wait_for(std::atomic<bool>& flag, const char* step) {
    for(int i=0;i<200 && !flag;i++) std::this_thread::sleep_for(std::chrono::milliseconds(100));
    if(!flag) {std::printf("TIMEOUT %s\n",step);std::fflush(stdout);std::_Exit(2);}
}
int main(int argc,char** argv) {
    if(argc!=5) return 10;
    if(!dlopen(argv[1],RTLD_NOW|RTLD_GLOBAL)) {puts(dlerror());return 11;}
    void* net=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);
    if(!net) {puts(dlerror());return 12;}
    auto init=reinterpret_cast<BbNetInitFn>(dlsym(net,"bbnet_init"));
    auto resolve=reinterpret_cast<BbNetResolveFn>(dlsym(net,"bbnet_resolve"));
    auto start=reinterpret_cast<BbNetStartFn>(dlsym(net,"bbnet_start"));
    BbNetHost host{2,"/tmp","CUSA00900","Bloodborne","01.09",spawn,join,exit_thread,mapped};
    if(init(&host)!=0) return 13;
    if(!strcmp(argv[3],"load")) {puts("MODULE_LOADED");fflush(stdout);std::_Exit(0);}
    start();
    auto fn=[&]<typename T>(const char* nid) {auto addr=resolve(nid);if(!addr){puts("NID missing");std::_Exit(14);}return reinterpret_cast<T>(addr);};
#define NET_FN(name,nid) auto name=fn.operator()<decltype(&sceNpMatching2##name)>(nid)
    NET_FN(SignalingGetConnectionInfo,"twVupeaYYrk");
    NET_FN(Initialize,"10t3e5+JPnU"); NET_FN(CreateContext,"YfmpW719rMo");
    NET_FN(RegisterContextCallback,"fQQfP87I7hs"); NET_FN(RegisterSignalingCallback,"0UMeWRGnZKA");
    NET_FN(RegisterRoomEventCallback,"p+2EnxmaAMM");
    NET_FN(ContextStart,"7vjNQ6Z1op0"); NET_FN(CreateJoinRoom,"zCWZmXXN600"); NET_FN(JoinRoom,"CSIMDsVjs-g");
    OrbisNpMatching2InitializeParameter settings{};settings.size=sizeof(settings);
    if(Initialize(&settings)) return 15;
    OrbisNpId identity{};SetNpId(identity,std::getenv("BB_SHADNET_NPID"));
    OrbisNpMatching2CreateContextParameter param{&identity,nullptr,nullptr,0,sizeof(param)};
    using namespace Libraries::Np::NpSignaling;
    auto sig_init=fn.operator()<decltype(&sceNpSignalingInitialize)>("3KOuC4RmZZU");
    auto sig_context=fn.operator()<decltype(&sceNpSignalingCreateContext)>("5yYjEdd4t8Y");
    auto sig_activate=fn.operator()<decltype(&sceNpSignalingActivateConnection)>("0UvTFeomAUM");
    if(sig_init(131072,700,48,16384))std::_Exit(30);
    OrbisNpSignalingContextId sig_ctx{};OrbisNpSignalingConnectionId sig_conn{};
    OrbisNpId peer_id{};SetNpId(peer_id,!strcmp(argv[3],"host")?"regressguest":"regresshost");
    if(sig_context(&identity,reinterpret_cast<void*>(sig1_cb),nullptr,&sig_ctx))std::_Exit(31);
    if(sig_activate(sig_ctx,&peer_id,&sig_conn))std::_Exit(32);
    wait_for(sig1_ready,"Sig1 connection");
    OrbisNpMatching2ContextId ctx{};
    if(CreateContext(&param,&ctx))return 16;
    RegisterContextCallback(context_cb,nullptr);RegisterSignalingCallback(ctx,signaling_cb,nullptr);RegisterRoomEventCallback(ctx,room_cb,nullptr);
    if(ContextStart(ctx,0))return 17;
    wait_for(started,"context");
    OrbisNpMatching2RequestOptParam opt{request_cb,nullptr,30000000,0,{}};
    OrbisNpMatching2RequestId req{};
    if(!strcmp(argv[3],"host")) {
        OrbisNpMatching2CreateJoinRoomRequest create{};create.maxSlot=5;create.worldId=10005;
        if(CreateJoinRoom(ctx,&create,&opt,&req))return 18;
    } else {
        OrbisNpMatching2JoinRoomRequest request{};request.roomId=std::strtoull(argv[4],nullptr,10);
        if(!strcmp(argv[4],"wait")) {unsigned long long input{};if(std::scanf("%llu",&input)!=1)std::_Exit(33);request.roomId=input;}
        if(JoinRoom(ctx,&request,&opt,&req))return 19;
    }
    wait_for(joined,"room reply");wait_for(established,"room signaling");
    puts("MATCHING2_ESTABLISHED");std::fflush(stdout);
    using namespace Libraries::Net;
    OrbisNpMatching2SignalingConnectionInfo info{};
    if(SignalingGetConnectionInfo(ctx,room.load(),peer_member.load(),
        ORBIS_NP_MATCHING2_SIGNALING_CONN_INFO_PEER_ADDR,&info)) return 20;
    auto sock_fn=fn.operator()<decltype(&sceNetSocket)>("Q4qBuN-c0ZM");
    auto bind_fn=fn.operator()<decltype(&sceNetBind)>("bErx49PgxyY");
    auto option_fn=fn.operator()<decltype(&sceNetSetsockopt)>("2mKX2Spso7I");
    auto send_fn=fn.operator()<decltype(&sceNetSendto)>("gvD1greCu0A");
    auto recv_fn=fn.operator()<decltype(&sceNetRecvfrom)>("304ooNZxWDY");
    auto sock=sock_fn("bbglorp-regression-gameplay",ORBIS_NET_AF_INET,ORBIS_NET_SOCK_DGRAM_P2P,0);
    OrbisNetSockaddrIn local{};local.sin_len=sizeof(local);local.sin_family=ORBIS_NET_AF_INET;
    local.sin_port=htons(3658);local.sin_vport=htons(30);
    int bind_result=bind_fn(sock,reinterpret_cast<OrbisNetSockaddr*>(&local),sizeof(local));
    if(bind_result) {std::printf("BIND_ERROR %x\n",bind_result);std::fflush(stdout);std::_Exit(21);}
    int nonblocking=1;
    if(option_fn(sock,ORBIS_NET_SOL_SOCKET,ORBIS_NET_SO_NBIO,&nonblocking,sizeof(nonblocking)))std::_Exit(22);
    OrbisNetSockaddrIn remote=local;remote.sin_addr=info.address.addr;remote.sin_port=info.address.port;
    constexpr char message[]="bbglorp-gameplay-datagram";
    bool received=false;
    for(int i=0;i<100 && !received;i++) {
        send_fn(sock,message,sizeof(message),0,reinterpret_cast<OrbisNetSockaddr*>(&remote),sizeof(remote));
        char buffer[128]{};OrbisNetSockaddrIn from{};u32 len=sizeof(from);
        int n=recv_fn(sock,buffer,sizeof(buffer),0,reinterpret_cast<OrbisNetSockaddr*>(&from),&len);
        received=n==sizeof(message) && !std::memcmp(buffer,message,sizeof(message)) &&
                 from.sin_addr==remote.sin_addr && from.sin_vport==remote.sin_vport;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    if(!received) {puts("TIMEOUT gameplay datagram");std::fflush(stdout);std::_Exit(23);}
    puts("GAMEPLAY_DATAGRAM_RECEIVED");std::fflush(stdout);
    std::this_thread::sleep_for(std::chrono::seconds(3));std::_Exit(0);
}
