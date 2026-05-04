git add .
git commit -m "Wedge angle warnings on Riser Pad: value input flips warn (>10 deg) then err (>15 deg) so users get an ambient cue while dialing in. Info-icon tooltip carries the threshold explanation. Plus deepened --err red (#e55353 -> #f04a3c) for stronger contrast against the navy palette — warm-shifted, ~85% saturation, sits in the same hue lane as the octopus-orange mesh; cascades to all existing err usages (validation messages, the Thin end stat when invalid, etc.)"
git push origin main
