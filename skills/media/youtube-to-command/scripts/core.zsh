# Shared player for youtube-to-command. Needs sox (`play`): brew install sox
# State lives in ${XDG_STATE_HOME:-~/.local/state}/youtube-to-command/<tag>.*
_yt2cmd_stop() {
  local pid
  [[ -f $1 ]] && pid=$(<"$1") && [[ -n $pid ]] && kill "$pid" 2>/dev/null
  rm -f "$1"
}

_yt2cmd_start() { # file offset vol loop pidf startf
  local file=$1 off=$2 vol=$3 loop=$4 pidf=$5 startf=$6
  local gain=$(printf '%.1f' $(( (vol + 1) / 10.0 )))
  local -a fx=()
  if [[ $loop == loop ]]; then fx=(repeat 9999); off=0; else fx=(trim "$off"); fi
  play -q -v "$gain" "$file" "${fx[@]}" >/dev/null 2>&1 &!
  print -r -- $! > "$pidf"
  print -r -- $(( $(date +%s) - off )) > "$startf"
}

# _yt2cmd <tag> <label> <file> <secs> <mm:ss> <loop|-> "<args>"
#   (no args)        toggle on/off
#   0-9              volume 10%-100% (keeps position if playing)
#   p                pause / resume at the same spot
#   next|prev [min]  skip forward/back (default 3 min; not for loops)
_yt2cmd() {
  local tag=$1 label=$2 file=$3 secs=$4 mmss=$5 loop=$6
  local -a w=(${=7})
  local cmd=$w[1]
  local sd="${XDG_STATE_HOME:-$HOME/.local/state}/youtube-to-command"
  mkdir -p "$sd"
  local pidf="$sd/$tag.pid" volf="$sd/$tag.vol" startf="$sd/$tag.start" pausef="$sd/$tag.paused"
  [[ -f $file ]] || { echo "$tag: missing file: $file (check ~/.Trash)" >&2; return 1; }
  command -v play >/dev/null || { echo "$tag: needs sox - brew install sox" >&2; return 1; }

  local pid="" playing=0 pos=0 vol=5
  [[ -f $volf ]] && vol=$(<"$volf")
  [[ -f $pidf ]] && pid=$(<"$pidf")
  if [[ -n $pid ]] && kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o command= 2>/dev/null | grep -qF -- "$file"; then
    playing=1
    pos=$(( $(date +%s) - $(<"$startf") ))
    (( pos < 0 )) && pos=0
  fi

  case $cmd in
    "")
      if (( playing )); then
        _yt2cmd_stop "$pidf"; echo "$label off"
      else
        rm -f "$pausef"; _yt2cmd_start "$file" 0 "$vol" "$loop" "$pidf" "$startf"
        echo "$label on ($mmss, volume $(( (vol + 1) * 10 ))%)"
      fi ;;
    [0-9])
      vol=$cmd; print -r -- "$vol" > "$volf"
      if (( playing )); then _yt2cmd_stop "$pidf"; else pos=0; rm -f "$pausef"; fi
      _yt2cmd_start "$file" "$pos" "$vol" "$loop" "$pidf" "$startf"
      echo "$label volume $(( (vol + 1) * 10 ))%" ;;
    p)
      if (( playing )); then
        print -r -- "$pos" > "$pausef"; _yt2cmd_stop "$pidf"; echo "$label paused"
      elif [[ -f $pausef ]]; then
        _yt2cmd_start "$file" "$(<"$pausef")" "$vol" "$loop" "$pidf" "$startf"; rm -f "$pausef"
        echo "$label resumed"
      fi ;;
    next|prev)
      (( playing )) || { echo "$label is not playing"; return 0; }
      [[ $loop == loop ]] && { echo "$label loops; skip not supported"; return 0; }
      local mins=${w[2]:-3} np
      if [[ $cmd == next ]]; then np=$(( pos + mins * 60 )); else np=$(( pos - mins * 60 )); fi
      np=${np%.*}
      (( np < 0 )) && np=0
      _yt2cmd_stop "$pidf"
      if (( np >= secs )); then echo "$label ended"; else _yt2cmd_start "$file" "$np" "$vol" "$loop" "$pidf" "$startf"; echo "$label at $(( np / 60 )):$(printf '%02d' $(( np % 60 )))"; fi ;;
    *) echo "usage: $tag [0-9 | p | next|prev [mins]]" >&2; return 2 ;;
  esac
}
