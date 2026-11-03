// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstdint>
#include <span>

namespace Libraries::Np::NpSignaling {

enum class PacketEnvelope { Invalid, StunEcho, Signaling };

// STUN replies have no magic and are six bytes. BBSC's empty progress snapshot is also
// six bytes (SHAD, 0x26, 0), so length alone cannot distinguish these protocols.
inline PacketEnvelope ClassifyPacketEnvelope(std::span<const std::uint8_t> packet,
                                             std::uint32_t from_addr, std::uint16_t from_port,
                                             std::uint32_t server_addr, std::uint16_t server_port) {
    if (packet.size() >= 5 && packet[0] == 'S' && packet[1] == 'H' &&
        packet[2] == 'A' && packet[3] == 'D') {
        return PacketEnvelope::Signaling;
    }
    if (packet.size() == 6 && server_addr != 0 && server_port != 0 &&
        from_addr == server_addr && from_port == server_port) {
        return PacketEnvelope::StunEcho;
    }
    return PacketEnvelope::Invalid;
}

} // namespace Libraries::Np::NpSignaling
