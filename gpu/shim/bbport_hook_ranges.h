// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
#include <map>
#include <iterator>

// Half-open byte ranges: adjacent hooks are legal; any shared byte is not.
class BbHookRanges {
    std::map<std::uintptr_t, std::size_t> ranges;
public:
    bool Overlaps(std::uintptr_t begin, std::size_t size) const {
        auto next = ranges.lower_bound(begin);
        if (next != ranges.end() && next->first - begin < size) return true;
        if (next != ranges.begin()) {
            const auto previous = std::prev(next);
            if (begin - previous->first < previous->second) return true;
        }
        return false;
    }
    void Add(std::uintptr_t begin, std::size_t size) { ranges.emplace(begin, size); }
};
