// SPDX-License-Identifier: GPL-2.0-or-later
#include <array>
#include <cassert>
#include "core/libraries/np/np_signaling/np_signaling_packet.h"
using namespace Libraries::Np::NpSignaling;
int main() {
    constexpr std::uint32_t server = 0x0100007f, peer = 0x0200007f;
    constexpr std::uint16_t port = 31314;
    const std::array<std::uint8_t, 6> progress{'S', 'H', 'A', 'D', 0x26, 0};
    assert(ClassifyPacketEnvelope(progress, peer, 3658, server, port) ==
           PacketEnvelope::Signaling);
    // Even server-origin packets retain their BBSC envelope, including an empty snapshot.
    assert(ClassifyPacketEnvelope(progress, server, port, server, port) ==
           PacketEnvelope::Signaling);
    const std::array<std::uint8_t, 6> echo{192, 0, 2, 1, 0x0e, 0x4a};
    assert(ClassifyPacketEnvelope(echo, server, port, server, port) == PacketEnvelope::StunEcho);
    assert(ClassifyPacketEnvelope(echo, peer, port, server, port) == PacketEnvelope::Invalid);
    assert(ClassifyPacketEnvelope(echo, server, port + 1, server, port) == PacketEnvelope::Invalid);
    assert(ClassifyPacketEnvelope(echo, 0, 0, 0, 0) == PacketEnvelope::Invalid);
    assert(ClassifyPacketEnvelope(std::span(echo).first(5), server, port, server, port) ==
           PacketEnvelope::Invalid);
    assert(ClassifyPacketEnvelope(std::span(echo).first(0), server, port, server, port) ==
           PacketEnvelope::Invalid);
}
