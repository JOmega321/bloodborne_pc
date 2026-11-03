// SPDX-License-Identifier: GPL-2.0-or-later
#include "../gpu/shim/bbport_hook_ranges.h"
#include <cassert>
int main() {
    BbHookRanges ranges;
    ranges.Add(0x1384500, 16);
    assert(!ranges.Overlaps(0x1384510, 16)); // adjacent BBSC summon callbacks
    assert(ranges.Overlaps(0x138450f, 16));
    assert(ranges.Overlaps(0x1384500, 5));
    assert(ranges.Overlaps(0x13844fc, 5));
    assert(!ranges.Overlaps(0x13844fb, 5));
    ranges.Add(0x1384510, 16);
    assert(!ranges.Overlaps(0x1384520, 16));
    ranges.Add(0x2000000, 40); // previous hook can be longer than 16 bytes
    assert(ranges.Overlaps(0x2000020, 5));
    assert(!ranges.Overlaps(0x2000028, 5));
}
