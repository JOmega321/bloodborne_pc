// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Mute diagnostics only. The test compiles the production relay and endpoint code unchanged.
#define LOG_INFO(...) ((void)0)
#define LOG_WARNING(...) ((void)0)
