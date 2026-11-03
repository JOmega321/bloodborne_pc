// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <cassert>
#include <string_view>
#include <arpa/inet.h>
namespace Core::Bloodborne { void BbscTimelineEvent(std::string_view, std::string_view) {} }
#include "core/net/p2p_codec.h"
using namespace Core::Net::P2P;
int main() {
    auto keys = std::make_shared<Keyring>();
    FramingCodec codec(keys);
    auto server = Endpoint::IPv4("127.0.0.1", 31314);
    auto peer = Endpoint::IPv4("127.0.0.2", 3658);
    std::array<u8, 21> ping{};ping[0]=1;
    // An unconfigured endpoint always uses the normal PS4 framing.
    assert(codec.EncodeSignaling(ping,server).size()==27);
    keys->SetStunServer(inet_addr("127.0.0.1"),htons(31314));
    auto wire = codec.EncodeSignaling(ping,server);
    assert(wire.size()==25);
    for(int i=0;i<4;i++)assert(wire[i]==0xFF);
    assert(std::equal(ping.begin(),ping.end(),wire.begin()+4));
    assert(codec.EncodeSignaling(ping,peer).size()==27);
    // The exact response emitted by the official BBSC 0.0.2 shadNet server.
    const std::array<u8,10> echo{0xFF,0xFF,0xFF,0xFF,127,0,0,1,0x0e,0x4a};
    auto reply=codec.Decode(echo,server);
    assert(reply.kind==Codec::Kind::Signaling);
    assert(reply.payload==std::vector<u8>(echo.begin()+4,echo.end()));
    assert(codec.Decode(echo,peer).kind==Codec::Kind::Invalid);
    assert(codec.Decode(echo,Endpoint::IPv4("127.0.0.1",31315)).kind==Codec::Kind::Invalid);
    assert(codec.Decode(std::span(echo).first(9),server).kind==Codec::Kind::Invalid);
    // BBSC progress from a peer keeps the modern signaling envelope and payload.
    const std::array<u8,6> progress{'S','H','A','D',0x26,0};
    auto framed=codec.EncodeSignaling(progress,peer);
    auto decoded=codec.Decode(framed,peer);
    assert(decoded.kind==Codec::Kind::Signaling);
    assert(decoded.payload==std::vector<u8>(progress.begin(),progress.end()));
    // Peer gameplay traffic retains communication-id and cryptographic validation.
    keys->SetCommunicationId(CommunicationId{1,2,3,4});
    keys->SetPeerKey(peer,P2PKey{});
    const std::array<u8,3> payload{9,8,7};
    auto datagram=codec.EncodeDatagram(30,30,payload,peer,{true,true});
    auto received=codec.Decode(datagram,peer);
    assert(received.kind==Codec::Kind::Datagram);
    assert(received.payload==std::vector<u8>(payload.begin(),payload.end()));
    auto wrong_id=datagram;wrong_id[6]^=1;
    assert(codec.Decode(wrong_id,peer).kind==Codec::Kind::Invalid);
    datagram.back()^=1;
    assert(codec.Decode(datagram,peer).kind==Codec::Kind::Invalid);
    keys->SetStunServer(0,0);
    assert(codec.Decode(echo,server).kind==Codec::Kind::Invalid);
}
