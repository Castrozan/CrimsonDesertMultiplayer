#include "mod/agent/agent_state.h"

#include <cmath>
#include <format>

namespace cdmp::agent {

namespace {

std::string number(float value) {
    if (!std::isfinite(value)) return "null";
    return std::format("{:.4f}", value);
}

std::string vector(const proto::Vec3& v) {
    return std::format("[{},{},{}]", number(v.x), number(v.y), number(v.z));
}

std::string quaternion(const proto::Quat& q) {
    return std::format("[{},{},{},{}]", number(q.x), number(q.y), number(q.z), number(q.w));
}

std::string player_json(const PlayerView& player) {
    return std::format(
        R"({{"position":{},"rotation":{},"health":{},"health_max":{},"stamina":{},"stamina_max":{},"static_position_error":{}}})",
        vector(player.position), quaternion(player.rotation), number(player.health), number(player.health_max),
        number(player.stamina), number(player.stamina_max), number(player.static_position_error));
}

std::string camera_json(const CameraView& camera) {
    return std::format(R"({{"position":{},"forward":{},"right":{}}})", vector(camera.position),
                       vector(camera.forward), vector(camera.right));
}

std::string actors_json(const std::vector<ActorView>& actors) {
    std::string joined;
    for (const ActorView& actor : actors) {
        if (!joined.empty()) joined += ',';
        joined += std::format(R"({{"key":"0x{:08X}","kind":"{}","position":{},"distance":{}}})", actor.key,
                              actor.kind, vector(actor.position), number(actor.distance));
    }
    return "[" + joined + "]";
}

}  // namespace

std::string escape_json(std::string_view text) {
    std::string escaped;
    escaped.reserve(text.size());
    for (const char character : text) {
        const auto byte = static_cast<unsigned char>(character);
        if (character == '"' || character == '\\') {
            escaped += '\\';
            escaped += character;
        } else if (byte < 0x20) {
            escaped += std::format("\\u{:04x}", byte);
        } else {
            escaped += character;
        }
    }
    return escaped;
}

std::string to_json(const AgentState& state) {
    return std::format(
        R"({{"sequence":{},"uptime_ms":{},"in_world":{},"player":{},"player_status":"{}","camera":{},"camera_status":"{}","velocity":{},"actors":{},"paused":{}}})",
        state.sequence, state.uptime_ms, state.player ? "true" : "false",
        state.player ? player_json(*state.player) : "null", escape_json(state.player_status),
        state.camera ? camera_json(*state.camera) : "null", escape_json(state.camera_status),
        state.velocity ? vector(*state.velocity) : "null", actors_json(state.actors),
        state.paused ? "true" : "false");
}

}  // namespace cdmp::agent
