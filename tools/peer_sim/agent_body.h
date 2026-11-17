#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "common/protocol.h"

namespace cdmp::peer {

class AgentBody {
public:
    void observe_player_state(const proto::PlayerState& state);
    void observe_player_move(const std::vector<uint8_t>& move_request, uint32_t now_ms);

    void advance(uint32_t now_ms);
    std::optional<std::vector<uint8_t>> move_request(uint32_t now_ms) const;
    std::optional<proto::PlayerState> state() const;

    std::string command(std::string_view line);

private:
    std::string describe() const;

    std::optional<proto::PlayerState> player_;
    std::vector<uint8_t> move_template_;
    uint64_t template_timestamp_ = 0;
    uint32_t template_received_ms_ = 0;

    bool placed_ = false;
    proto::Vec3 position_{};
    float yaw_radians_ = 0.0f;
    std::optional<proto::Vec3> target_;
    float speed_metres_per_second_ = 3.0f;
    bool follow_ground_of_player_ = true;
    uint32_t advanced_ms_ = 0;
};

}  // namespace cdmp::peer
