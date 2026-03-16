#!/bin/bash
# Download credit agreement documents using curl (handles SSL better on macOS)
set -euo pipefail

OUTPUT_DIR="/Users/ashrit/Desktop/Credit_Agreement_Parsing/raw_documents"
CSV_FILE="/Users/ashrit/Desktop/Credit_Agreement_Parsing/corporate_credit_agreement_source_urls_50.csv"

mkdir -p "$OUTPUT_DIR"

SUCCESS=0
FAILED=0
TOTAL=0

# Read CSV, skip header
tail -n +2 "$CSV_FILE" | while IFS= read -r url; do
    url=$(echo "$url" | tr -d '\r' | xargs)
    [ -z "$url" ] && continue

    TOTAL=$((TOTAL + 1))
    IDX=$(printf "%03d" $TOTAL)

    # Extract filename from URL
    BASENAME=$(echo "$url" | sed 's|.*/||' | sed 's|%20|_|g' | sed 's|[^a-zA-Z0-9._-]|_|g')

    # Trim length
    if [ ${#BASENAME} -gt 80 ]; then
        BASENAME="${BASENAME:0:80}"
    fi

    OUTFILE="${IDX}_${BASENAME}"
    OUTPATH="${OUTPUT_DIR}/${OUTFILE}"

    if [ -f "$OUTPATH" ]; then
        echo "[${IDX}/049] SKIP (exists): ${OUTFILE}"
        SUCCESS=$((SUCCESS + 1))
        continue
    fi

    echo "[${IDX}/049] Downloading: ${OUTFILE}"
    echo "         URL: ${url:0:100}..."

    HTTP_CODE=$(curl -L -s -o "$OUTPATH" -w "%{http_code}" \
        --max-time 60 \
        --retry 2 \
        --retry-delay 3 \
        -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
        "$url" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ] && [ -f "$OUTPATH" ]; then
        SIZE=$(du -k "$OUTPATH" | cut -f1)
        if [ "$SIZE" -gt 0 ]; then
            echo "         OK (${SIZE} KB, HTTP ${HTTP_CODE})"
            SUCCESS=$((SUCCESS + 1))
        else
            echo "         FAILED: Empty file"
            rm -f "$OUTPATH"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "         FAILED: HTTP ${HTTP_CODE}"
        rm -f "$OUTPATH"
        FAILED=$((FAILED + 1))
    fi

    sleep 0.3
done

echo ""
echo "========================================="
echo "Download complete."
ls -1 "$OUTPUT_DIR" | wc -l | xargs echo "Files in raw_documents:"
