#!/bin/bash
# Retry SEC.gov and other failed downloads with proper headers
# SEC requires User-Agent with company name and email per their fair access policy

OUTPUT_DIR="/Users/ashrit/Desktop/Credit_Agreement_Parsing/raw_documents"
CSV_FILE="/Users/ashrit/Desktop/Credit_Agreement_Parsing/corporate_credit_agreement_source_urls_50.csv"

SEC_UA="CreditAgreementParser/1.0 (research@example.com)"
BROWSER_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

TOTAL=0

tail -n +2 "$CSV_FILE" | while IFS= read -r url; do
    url=$(echo "$url" | tr -d '\r' | xargs)
    [ -z "$url" ] && continue

    TOTAL=$((TOTAL + 1))
    IDX=$(printf "%03d" $TOTAL)

    BASENAME=$(echo "$url" | sed 's|.*/||' | sed 's|%20|_|g' | sed 's|[^a-zA-Z0-9._-]|_|g')
    if [ ${#BASENAME} -gt 80 ]; then
        BASENAME="${BASENAME:0:80}"
    fi
    OUTFILE="${IDX}_${BASENAME}"
    OUTPATH="${OUTPUT_DIR}/${OUTFILE}"

    # Skip already downloaded
    if [ -f "$OUTPATH" ]; then
        continue
    fi

    echo "[${IDX}/049] Retrying: ${OUTFILE}"

    # Use SEC-compliant User-Agent for sec.gov
    if echo "$url" | grep -q "sec.gov"; then
        HTTP_CODE=$(curl -L -s -o "$OUTPATH" -w "%{http_code}" \
            --max-time 60 --retry 2 --retry-delay 3 \
            -A "$SEC_UA" \
            -H "Accept-Encoding: gzip, deflate" \
            "$url" 2>/dev/null || echo "000")
    else
        HTTP_CODE=$(curl -L -s -o "$OUTPATH" -w "%{http_code}" \
            --max-time 60 --retry 2 --retry-delay 3 \
            -A "$BROWSER_UA" \
            "$url" 2>/dev/null || echo "000")
    fi

    if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ] && [ -f "$OUTPATH" ]; then
        SIZE=$(du -k "$OUTPATH" | cut -f1)
        if [ "$SIZE" -gt 0 ]; then
            echo "         OK (${SIZE} KB, HTTP ${HTTP_CODE})"
        else
            echo "         FAILED: Empty file"
            rm -f "$OUTPATH"
        fi
    else
        echo "         FAILED: HTTP ${HTTP_CODE}"
        rm -f "$OUTPATH"
    fi

    sleep 0.5
done

echo ""
echo "========================================="
echo "Total files now:"
ls -1 "$OUTPUT_DIR" | wc -l
