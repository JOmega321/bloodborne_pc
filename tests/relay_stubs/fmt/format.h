// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <string>
#include <string_view>
namespace fmt {
template <typename... Args> std::string format(std::string_view, Args&&...) { return {}; }
}
