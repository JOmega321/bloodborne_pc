// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstdint>
#include <cstring>
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

// BBSC life state: "SHAD" 0x23 + u32 player + u8 dead + u32 sequence, sent twice a second by every
// player in a session, the host and its guests alike.
struct BbscLifeReport {
    std::uint32_t player = 0;
    std::uint8_t dead = 0;
    std::uint32_t sequence = 0;
};

inline bool ParseBbscLifePacket(std::span<const std::uint8_t> packet, BbscLifeReport& report) {
    if (packet.size() < 14 || std::memcmp(packet.data(), "SHAD", 4) != 0 || packet[4] != 0x23) {
        return false;
    }
    std::memcpy(&report.player, packet.data() + 5, 4);
    report.dead = packet[9];
    std::memcpy(&report.sequence, packet.data() + 10, 4);
    return true;
}

} // namespace Libraries::Np::NpSignaling
