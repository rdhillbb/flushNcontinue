#!/bin/bash
# ============================================================================
# Session Time Check — Run at the start of every Claude Code session
# Establishes current date, day of week, and time in both Cambodia and US
# ============================================================================

echo "============================================"
echo "  Session Time Reference"
echo "============================================"
echo ""

KHT_FULL=$(TZ='Asia/Phnom_Penh' date '+%A, %B %d, %Y %I:%M %p')
KHT_SHORT=$(TZ='Asia/Phnom_Penh' date '+%Y-%m-%d %H:%M')
KHT_DAY=$(TZ='Asia/Phnom_Penh' date '+%A')

EST_FULL=$(TZ='America/New_York' date '+%A, %B %d, %Y %I:%M %p %Z')
EST_SHORT=$(TZ='America/New_York' date '+%Y-%m-%d %H:%M')
EST_DAY=$(TZ='America/New_York' date '+%A')

UTC_SHORT=$(TZ='UTC' date '+%Y-%m-%d %H:%M UTC')

# Some shells (e.g. Git Bash on Windows) lack time-zone data and silently print UTC.
TZ_WARN=""
[ "$(TZ='America/New_York' date '+%z')" = "+0000" ] && TZ_WARN="  ⚠  This shell has no time-zone data: the Cambodia and US times below are really UTC."

[ -n "$TZ_WARN" ] && echo "$TZ_WARN" && echo ""
echo "  Cambodia (KHT, UTC+7):"
echo "    $KHT_FULL"
echo ""
echo "  US Eastern (EST/EDT):"
echo "    $EST_FULL"
echo ""
echo "  UTC:"
echo "    $UTC_SHORT"
echo ""

# Highlight if dates differ between timezones
if [ "$KHT_DAY" != "$EST_DAY" ]; then
    echo "  ⚠  DATE MISMATCH: Cambodia is on $KHT_DAY, US is still on $EST_DAY"
    echo ""
fi

# Deploy window: NOT hard-coded here (it differs per project and went stale, C-37).
# If the current project has a deploy-window hook, show its answer; it is the real gate.
if [ -f scripts/hooks/check-deploy-window.sh ]; then
    if WINDOW_RESULT="$(bash scripts/hooks/check-deploy-window.sh 2>&1)"; then
        echo "  ✓ Deploy window (project hook): $WINDOW_RESULT"
    else
        echo "  ✗ Deploy window (project hook): $WINDOW_RESULT"
    fi
fi

echo ""
echo "  DB queries: use UTC timestamps"
# US Eastern day boundary in UTC, from the live offset (04:00 UTC in EDT, 05:00 UTC in EST)
OFF=$(TZ='America/New_York' date '+%z')            # e.g. -0400
BH=$((10#${OFF:1:2}))
ET_TODAY=$(TZ='America/New_York' date '+%Y-%m-%d')
ET_ZONE=$(TZ='America/New_York' date '+%Z')
printf "  US Eastern day boundary today (%s): %02d:00 UTC
" "$ET_ZONE" "$BH"
printf "  Example: %s ET = created_at >= '%s %02d:00:00' (UTC), up to the next day's boundary
" "$ET_TODAY" "$ET_TODAY" "$BH"
echo "  Safer in SQL: (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'America/New_York')::date"
echo "============================================"
