#!/usr/bin/env bash
set -euo pipefail
mkdir -p static/img
mk(){ cat > "static/img/$1.svg" <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400">
  <defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="$3" offset="0"/><stop stop-color="#111" offset="1"/></linearGradient></defs>
  <rect width="100%" height="100%" fill="url(#g)"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-size="48" fill="white" opacity="0.9">$2</text>
</svg>
SVG
}
mk card_photos "Photos" "#6aa0ff"
mk card_videos "Vidéos" "#ff6a95"
mk card_events "Événements" "#ffc36a"
mk card_albums "Albums" "#6affbf"
mk card_docs   "Documents" "#a06aff"
mk card_admin  "Admin" "#6afff0"
echo "✅ SVG créés dans static/img/"
