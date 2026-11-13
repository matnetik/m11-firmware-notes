#!/usr/bin/env python3
"""Rebuild the user's exported settings.lcse from the verbatim copy in context
(the SD card unmounted before it could be cp'd). s7(v)=[v]*7 per-profile array;
index 0 = live/current, indices 1..6 = User Profiles 1..6."""
import json, collections

def s7(v): return [v] * 7

S = collections.OrderedDict()
S["D010"] = s7(12500)
S["5013"] = s7(0)
S["D000"] = s7(300)
S["D001"] = s7(2)
S["D06E"] = s7(0)
S["D002"] = s7("L10")
S["500A"] = s7(2)
S["D1AB"] = [105, 3, 105, 116, 131]
S["D1AC"] = [5, 3, 105, 116, 131]
S["D1AD"] = [55, 0]
S["D003"] = s7(0)
S["D004"] = [2, 2, 0, 0, 0, 0, 0]
S["500B"] = s7(2)
S["5010"] = s7(0)
S["D041"] = s7(0)
S["D006"] = s7(3)
S["D007"] = s7(1000)
S["D009"] = s7(0)
S["D198"] = [0, 0, 1, 1, 1, 1, 1]
S["D00B"] = [12500, 12500, 3200, 3200, 3200, 3200, 3200]
S["D0D3"] = s7(200)
S["D00C"] = s7(32770)
S["D00F"] = s7(3)
S["D081"] = s7(1)
S["D1F4"] = s7(0)
S["D13E"] = s7(1)
S["D08A"] = [-1, -1, 0, 0, 0, 0, 0]
S["D08B"] = s7(0)
S["D08C"] = [1, 1, 0, 0, 0, 0, 0]
S["D08D"] = [1, 1, 0, 0, 0, 0, 0]
S["D08E"] = s7(0)
S["D08F"] = [1, 1, 0, 0, 0, 0, 0]
S["D090"] = s7(0)
S["D091"] = s7(0)
S["D092"] = s7(0)
S["D093"] = s7(0)
S["D094"] = s7(0)
S["D0B0"] = s7(0)
S["D0B1"] = s7(0)
S["D196"] = s7(0)
S["D050"] = s7(2)
S["5005"] = [1, 1, 0, 0, 0, 0, 0]
S["D014"] = s7(5000)
S["D130"] = s7(917)
S["D131"] = s7(256)
S["D132"] = s7(436)
S["D3D2"] = [1, 1, 0, 0, 0, 0, 0]
S["D3BC"] = [-15, -15, 0, 0, 0, 0, 0]
S["D3BD"] = [-15, -15, 0, 0, 0, 0, 0]
S["D134"] = s7(1)
S["D017"] = s7(7)
S["D019"] = s7("LEICA")
S["D01A"] = [0, 0, 1, 1, 1, 1, 1]
S["D11E"] = s7(0)
S["D19E"] = s7(0)
S["D19F"] = s7(0)
S["D1A0"] = s7(0)
S["D085"] = s7(1)
S["D1A1"] = s7(1)
S["D1A2"] = s7(1)
S["D1A3"] = s7(1)
S["D165"] = s7(1)
S["D166"] = s7(0)
S["D167"] = s7(0)
S["D168"] = s7(0)
S["D139"] = s7(0)
S["D01D"] = s7(253)
S["D170"] = s7(0)
S["D173"] = s7(253)
S["D171"] = s7(0)
S["D175"] = s7(253)
S["D172"] = s7(0)
S["D174"] = s7(253)
S["D197"] = s7(0)
S["D01E"] = s7(15)
S["D133"] = s7(15)
S["D32B"] = s7(0)
S["D01F"] = s7(1)
S["D162"] = s7(1)
S["D163"] = s7(1)
S["D164"] = s7(1)
S["D1A5"] = s7(0)
S["D1A6"] = s7(0)
S["D1A7"] = s7(0)
S["D1A8"] = s7(0)
S["D0C4"] = s7(0)
S["D169"] = s7(0)
S["D16A"] = s7(0)
S["D16B"] = s7(0)
S["D15E"] = s7(1)
S["D15F"] = s7(0)
S["D160"] = s7(0)
S["D161"] = s7(0)
S["D07A"] = s7(1)
S["D07B"] = [0, 0, 1, 1, 1, 1, 1]
S["D020"] = [0, 0, 1, 1, 1, 1, 1]
S["D051"] = s7(30)
S["D108"] = s7(120)
S["D1E6"] = s7(2)
S["D077"] = s7(0)
S["D190"] = s7(1)
S["D191"] = s7(1)
S["D192"] = s7(0)
S["D193"] = [15, 15, 3, 3, 3, 3, 3]
S["D194"] = s7(0)
S["D195"] = s7(10)
S["D1D6"] = [84, 84, 21, 21, 21, 21, 21]
S["D1D7"] = s7(21)
S["D02F"] = s7(0)
S["501F"] = s7("Info")
S["501E"] = s7("Artist")
S["D031"] = s7(0)
S["D032"] = s7(1)
S["D033"] = s7(0)
S["D036"] = s7(0)
S["D124"] = [1]
S["D6B2"] = [2]
S["D037"] = ["User1"]
S["D038"] = ["User2"]
S["D039"] = ["User3"]
S["D03A"] = ["User4"]
S["D0AD"] = ["User5"]
S["D0AE"] = ["User6"]
S["D1FC"] = s7(2)
S["0342"] = s7(4)
S["D140"] = s7(1)
S["D115"] = [1, 1, 4, 4, 4, 4, 4]
S["D1A9"] = [13, 6, 53252, 6, 53566, 53328, 53536, 13, 13, 6, 53252, 6,
             53566, 53328, 53536, 13, 13, 0, 13, 0, 13, 0, 13, 0, 13, 0]
S["D0D5"] = s7(2)
S["D13A"] = [0, 0, 1, 1, 1, 1, 1]
S["D16C"] = s7(0)
S["D16D"] = s7(0)
S["D16E"] = s7(0)
S["D0A2"] = s7(0)
S["D097"] = s7(0)
S["D0C3"] = s7(1)
S["D1AA"] = s7(1)
S["D17A"] = s7(1)
S["D340"] = s7(0)

doc = collections.OrderedDict()
doc["Camera"] = "LEICA M11"
doc["Version"] = 3185
doc["Settings"] = S

json.dump(doc, open("profile_work/settings_original.lcse", "w"), indent=2)

# structural check
sevens = {k: v for k, v in S.items() if len(v) == 7}
others = {k: len(v) for k, v in S.items() if len(v) != 7}
print("total keys:", len(S))
print("7-element (per-profile) keys:", len(sevens))
print("non-7 keys:", others)
print("profile name keys:", {k: S[k] for k in ("D037","D038","D039","D03A","D0AD","D0AE")})
# which keys differ between profile-1 (idx1) and the untouched defaults (idx2..6)?
diffs = {k: v for k, v in sevens.items() if len(set(v[1:])) > 1}
print("\nkeys where profile 1 differs from default profiles 2-6:")
for k, v in diffs.items():
    print("  %s = %s" % (k, v))
