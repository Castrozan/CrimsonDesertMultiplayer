#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

#include "common/protocol.h"

namespace cdmp::agent {

struct PlayerView {
    proto::Vec3 position;
    proto::Quat rotation;
    float health = 0.0f;
    float health_max = 0.0f;
    float stamina = 0.0f;
    float stamina_max = 0.0f;
    float static_position_error = 0.0f;
};

struct CameraView {
    proto::Vec3 position;
    proto::Vec3 forward;
    proto::Vec3 right;
};

struct AgentState {
    uint64_t sequence = 0;
    uint64_t uptime_ms = 0;
    std::optional<PlayerView> player;
    std::string player_status;
    std::optional<CameraView> camera;
    std::string camera_status;
};

std::string to_json(const AgentState& state);

std::string escape_json(std::string_view text);

}  // namespace cdmp::agent
