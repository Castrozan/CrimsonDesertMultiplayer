#include "mod/agent/agent_server.h"

#include <winsock2.h>
#include <ws2tcpip.h>

#include <string>

#include "common/udp.h"
#include "mod/log.h"

namespace cdmp::agent {

namespace {

constexpr int kPollIntervalMs = 200;
constexpr size_t kMaxRequestBytes = 4096;

bool stop_requested(HANDLE stop_event) { return WaitForSingleObject(stop_event, 0) == WAIT_OBJECT_0; }

bool readable(SOCKET socket_handle) {
    fd_set readable_set;
    FD_ZERO(&readable_set);
    FD_SET(socket_handle, &readable_set);
    timeval timeout{0, kPollIntervalMs * 1000};
    return select(0, &readable_set, nullptr, nullptr, &timeout) > 0;
}

bool send_all(SOCKET socket_handle, const std::string& data) {
    size_t sent = 0;
    while (sent < data.size()) {
        const int result = send(socket_handle, data.data() + sent, static_cast<int>(data.size() - sent), 0);
        if (result <= 0) return false;
        sent += static_cast<size_t>(result);
    }
    return true;
}

std::string answer(std::string request, const StateProvider& provide_state) {
    while (!request.empty() && (request.back() == '\r' || request.back() == ' ')) request.pop_back();
    if (request == "state") return to_json(provide_state()) + "\n";
    return R"({"error":"unknown request, send \"state\""})" "\n";
}

void serve_client(SOCKET client, HANDLE stop_event, const StateProvider& provide_state) {
    std::string pending;
    char buffer[512];
    while (!stop_requested(stop_event)) {
        if (!readable(client)) continue;
        const int received = recv(client, buffer, sizeof buffer, 0);
        if (received <= 0) return;
        pending.append(buffer, static_cast<size_t>(received));
        if (pending.size() > kMaxRequestBytes) return;
        for (size_t newline = pending.find('\n'); newline != std::string::npos; newline = pending.find('\n')) {
            const std::string request = pending.substr(0, newline);
            pending.erase(0, newline + 1);
            if (!send_all(client, answer(request, provide_state))) return;
        }
    }
}

SOCKET listen_on_loopback(uint16_t port) {
    const SOCKET listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (listener == INVALID_SOCKET) return INVALID_SOCKET;
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(listener, reinterpret_cast<const sockaddr*>(&address), sizeof address) != 0 ||
        listen(listener, 1) != 0) {
        closesocket(listener);
        return INVALID_SOCKET;
    }
    return listener;
}

}  // namespace

void serve(uint16_t port, HANDLE stop_event, const StateProvider& provide_state) {
    if (!net::startup()) {
        log::error("Agent bridge: Winsock startup failed");
        return;
    }
    const SOCKET listener = listen_on_loopback(port);
    if (listener == INVALID_SOCKET) {
        log::error("Agent bridge: cannot listen on 127.0.0.1:{} ({})", port, net::UdpSocket::last_error());
        net::cleanup();
        return;
    }
    log::info("Agent bridge: listening on 127.0.0.1:{}", port);
    while (!stop_requested(stop_event)) {
        if (!readable(listener)) continue;
        const SOCKET client = accept(listener, nullptr, nullptr);
        if (client == INVALID_SOCKET) continue;
        log::info("Agent bridge: client connected");
        serve_client(client, stop_event, provide_state);
        closesocket(client);
        log::info("Agent bridge: client disconnected");
    }
    closesocket(listener);
    net::cleanup();
}

}  // namespace cdmp::agent
