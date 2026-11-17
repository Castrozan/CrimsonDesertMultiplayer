#include "agent_body.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <sstream>

#include "mod/game/offsets.h"

namespace cdmp::peer {
namespace {

namespace off = game::build_3663;

constexpr size_t kPosition = off::kMoveActor_Data + off::kMoveData_Pos;
constexpr size_t kRotation = off::kMoveActor_Data + off::kMoveData_Quat;
constexpr size_t kTimestamp = off::kMoveActor_Data + off::kMoveData_Timestamp;
constexpr size_t kPathLocalPosition = off::kMoveActor_Data + off::kMoveData_PathLocalPos;
constexpr size_t kPathLocalRotation = off::kMoveActor_Data + off::kMoveData_PathLocalQuat;
constexpr float kArrivalMetres = 0.15f;
constexpr float kSpawnOffsetMetres = 3.0f;
constexpr uint32_t kMaxStepMs = 250;
constexpr const char* kHelp =
    R"({"ok":true,"transport":"UDP, one command per datagram, one JSON datagram back","commands":{)"
    R"("state":"body position, yaw, moving, speed and the player's position",)"
    R"("goto X Z [SPEED]":"walk to the ground point in world metres, optional metres per second",)"
    R"("stop":"cancel the walk","teleport X Y Z":"place the body, height stays fixed",)"
    R"("face YAW_DEGREES":"turn, 0 is +Z and 90 is +X","speed METRES_PER_SECOND":"walking speed",)"
    R"("ground player|fixed":"height follows the player's or stays where teleport put it"}})";

proto::Quat yaw_quaternion(float yaw_radians) {
    return {0.0f, std::sin(yaw_radians * 0.5f), 0.0f, std::cos(yaw_radians * 0.5f)};
}

void write_vector(std::vector<uint8_t>& bytes, size_t offset, const proto::Vec3& value) {
    const float raw[3] = {value.x, value.y, value.z};
    std::memcpy(bytes.data() + offset, raw, sizeof raw);
}

void write_quaternion(std::vector<uint8_t>& bytes, size_t offset, const proto::Quat& value) {
    const float raw[4] = {value.x, value.y, value.z, value.w};
    std::memcpy(bytes.data() + offset, raw, sizeof raw);
}

}  // namespace

void AgentBody::observe_player_state(const proto::PlayerState& state) {
    player_ = state;
    if (placed_) return;
    position_ = {state.pos.x + kSpawnOffsetMetres, state.pos.y, state.pos.z};
    placed_ = true;
}

void AgentBody::observe_player_move(const std::vector<uint8_t>& move_request, uint32_t now_ms) {
    if (move_request.size() != off::kMoveActor_TailEnd && move_request.size() != off::kMoveActorReq_Size) return;
    move_template_ = move_request;
    std::memcpy(&template_timestamp_, move_request.data() + kTimestamp, sizeof template_timestamp_);
    template_received_ms_ = now_ms;
}

void AgentBody::advance(uint32_t now_ms) {
    const uint32_t elapsed_ms = advanced_ms_ ? now_ms - advanced_ms_ : 0;
    advanced_ms_ = now_ms;
    if (!placed_) return;
    if (follow_ground_of_player_ && player_) position_.y = player_->pos.y;
    if (!target_ || elapsed_ms == 0 || elapsed_ms > kMaxStepMs) return;
    const float dx = target_->x - position_.x, dz = target_->z - position_.z;
    const float distance = std::hypot(dx, dz);
    if (distance <= kArrivalMetres) {
        target_.reset();
        return;
    }
    yaw_radians_ = std::atan2(dx, dz);
    const float step = std::min(distance, speed_metres_per_second_ * static_cast<float>(elapsed_ms) / 1000.0f);
    position_.x += dx / distance * step;
    position_.z += dz / distance * step;
}

std::optional<std::vector<uint8_t>> AgentBody::move_request(uint32_t now_ms) const {
    if (!placed_ || move_template_.empty()) return std::nullopt;
    std::vector<uint8_t> request = move_template_;
    const proto::Quat rotation = yaw_quaternion(yaw_radians_);
    write_vector(request, kPosition, position_);
    write_vector(request, kPathLocalPosition, position_);
    write_quaternion(request, kRotation, rotation);
    write_quaternion(request, kPathLocalRotation, rotation);
    const uint64_t timestamp = template_timestamp_ + (now_ms - template_received_ms_);
    std::memcpy(request.data() + kTimestamp, &timestamp, sizeof timestamp);
    return request;
}

std::optional<proto::PlayerState> AgentBody::state() const {
    if (!placed_) return std::nullopt;
    proto::PlayerState state;
    state.pos = position_;
    state.rot = yaw_quaternion(yaw_radians_);
    state.health = player_ ? player_->health_max : 0.0f;
    state.health_max = player_ ? player_->health_max : 0.0f;
    state.flags = proto::kStateSynthetic;
    return state;
}

std::string AgentBody::describe() const {
    char text[320];
    std::snprintf(text, sizeof text,
                  "{\"ok\":true,\"placed\":%s,\"position\":[%.3f,%.3f,%.3f],\"yaw_degrees\":%.1f,\"moving\":%s,"
                  "\"speed\":%.2f,\"has_move_template\":%s,\"player_position\":[%.3f,%.3f,%.3f]}",
                  placed_ ? "true" : "false", position_.x, position_.y, position_.z,
                  yaw_radians_ * 57.29578f, target_ ? "true" : "false", speed_metres_per_second_,
                  move_template_.empty() ? "false" : "true", player_ ? player_->pos.x : 0.0f,
                  player_ ? player_->pos.y : 0.0f, player_ ? player_->pos.z : 0.0f);
    return text;
}

std::string AgentBody::command(std::string_view line) {
    std::istringstream words{std::string(line)};
    std::string verb;
    words >> verb;
    float a = 0.0f, b = 0.0f, c = 0.0f;
    if (verb == "help") return kHelp;
    if (verb == "state") return describe();
    if (verb == "stop") {
        target_.reset();
    } else if (verb == "goto" && (words >> a >> b)) {
        target_ = proto::Vec3{a, position_.y, b};
        if (words >> c && c > 0.0f) speed_metres_per_second_ = c;
    } else if (verb == "teleport" && (words >> a >> b >> c)) {
        position_ = {a, b, c};
        placed_ = true;
        follow_ground_of_player_ = false;
        target_.reset();
    } else if (verb == "face" && (words >> a)) {
        yaw_radians_ = a / 57.29578f;
    } else if (verb == "speed" && (words >> a) && a > 0.0f) {
        speed_metres_per_second_ = a;
    } else if (verb == "ground" && (words >> verb) && (verb == "player" || verb == "fixed")) {
        follow_ground_of_player_ = verb == "player";
    } else {
        return R"({"ok":false,"error":"unknown or malformed command; send help"})";
    }
    return R"({"ok":true})";
}

}  // namespace cdmp::peer
