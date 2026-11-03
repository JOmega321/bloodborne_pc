// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string_view>
#include "core/net/p2p_relay.h"
namespace Core::Bloodborne {
void BbscTimelineEvent(std::string_view, std::string_view) {}
}
using namespace Core::Net::P2P;
int main() {
#ifdef _WIN32
    WSADATA wsa{};
    assert(WSAStartup(MAKEWORD(2, 2), &wsa) == 0);
    _putenv_s("SHADPS4_P2P_RELAY", "");
#else
    unsetenv("SHADPS4_P2P_RELAY");
#endif
    // Production default: forced relay with direct copies.
    Relay relay;
    relay.SetServer(inet_addr("127.0.0.2"));
    relay.SetLocalId("test-host");
    relay.RememberPeer("test-guest", inet_addr("127.0.0.3"), htons(9000));
    auto peer = Endpoint::IPv4("127.0.0.3", 9000);
    auto server = Endpoint::IPv4("127.0.0.2", 3478);
    std::array<u8, 3> wire{1, 2, 3};
    int relayed = 0;
    auto send = [&](std::span<const u8>, const Endpoint&) { ++relayed; };
    assert(relay.Route(peer, wire, send) == Relay::Path::Both);
    assert(relayed == 1);
    // Registration ACK alone does not establish that the other player uses the UDP relay.
    const std::array<u8, 5> ack{'B', 'B', 'R', '1', 2};
    relay.OnReceive(ack, server);
    relay.OnReceive(wire, peer);
    // A direct reply used to set relayed=false, then default force_ immediately undid it,
    // suppressing all further direct packets even though no peer relay traffic had arrived.
    for (int i = 0; i < 5; ++i) {
        assert(relay.Route(peer, wire, send) == Relay::Path::Direct);
    }
    assert(relayed == 1);
    // Once real relayed peer traffic arrives, continue answering through the working relay.
    std::vector<u8> frame{'B', 'B', 'R', '1', 4};
    const std::string id = std::string("test-guest") + std::string(6, '\0');
    frame.insert(frame.end(), id.begin(), id.end());
    const u32 ip = inet_addr("127.0.0.3");
    const u16 port = htons(9000);
    const auto* bytes = reinterpret_cast<const u8*>(&ip);
    frame.insert(frame.end(), bytes, bytes + 4);
    bytes = reinterpret_cast<const u8*>(&port);
    frame.insert(frame.end(), bytes, bytes + 2);
    frame.insert(frame.end(), wire.begin(), wire.end());
    assert(relay.OnReceive(frame, server).unwrapped);
    assert(relay.Route(peer, wire, send) == Relay::Path::Relay);
    assert(relayed == 2);
    assert(relay.Route(Endpoint::IPv4("127.0.0.4", 9000), wire, send) == Relay::Path::Direct);
}
