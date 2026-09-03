#!/bin/bash
# Send a text and/or files to your own iMessage self-chat.
#   text-me.sh "message"                  -> text only
#   text-me.sh "message" file1 [file2...] -> text then files
#   text-me.sh "" file1                   -> files only
set -uo pipefail

TO="${TEXT_ME_TO:-${TEXT_ME_TO:?set TEXT_ME_TO to your iMessage number}}"
DB="$HOME/Library/Messages/chat.db"
STAGE="$HOME/Library/Messages/Attachments/_textme"

msg="${1-}"; shift || true

send_as() {  # $1 = absolute path
  osascript <<EOF
tell application "Messages" to send (POSIX file "$1" as alias) to participant "$TO"
EOF
}

if [ -n "$msg" ]; then
  # osascript exits 0 on a silent failure only for *delivery*; an Automation-permission
  # denial (-1743) does set a nonzero exit. Never swallow it - callers report success off this.
  if ! err=$(osascript -e "tell application \"Messages\" to send \"${msg//\"/\\\"}\" to participant \"$TO\"" 2>&1); then
    echo "send failed: $err" >&2
    exit 1
  fi
fi

[ $# -eq 0 ] && { echo "sent text"; exit 0; }

mkdir -p "$STAGE"
n=0
for f in "$@"; do
  [ -f "$f" ] || { echo "missing: $f" >&2; continue; }
  # Sandbox: Messages can only read a fixed set of paths. Staging here is the fix.
  cp "$f" "$STAGE/" || { echo "copy failed: $f" >&2; continue; }
  send_as "$STAGE/$(basename "$f")"
  n=$((n+1))
done
[ "$n" -eq 0 ] && { rmdir "$STAGE" 2>/dev/null; exit 1; }

# Wait for delivery: transfer_state 5 and error 0 on the last n outgoing attachments.
for _ in $(seq 1 60); do
  bad=$(sqlite3 "$DB" "select count(*) from (
      select m.is_sent, m.error, a.transfer_state
      from message m
      join message_attachment_join j on j.message_id=m.ROWID
      join attachment a on a.ROWID=j.attachment_id
      where a.is_outgoing=1 order by m.date desc limit $n)
    where is_sent<>1 or error<>0;" 2>/dev/null)
  [ "$bad" = "0" ] && break
  sleep 5
done

sqlite3 "$DB" "select case when is_sent=1 and error=0 then 'OK  ' else 'FAIL' end
    ||' '||round(total_bytes/1048576.0,1)||'MB  err='||error||'  '||f from (
    select m.is_sent, m.error, a.total_bytes, replace(a.filename,'$STAGE/','') f
    from message m
    join message_attachment_join j on j.message_id=m.ROWID
    join attachment a on a.ROWID=j.attachment_id
    where a.is_outgoing=1 order by m.date desc limit $n);"

rm -rf "$STAGE"
