set -eux
set -o pipefail

#!/bin/sh

# Download the latest backup from
# Heroku and gzip it

heroku pg:backups:download --output=/tmp/pg_backup.dump --app $APP_NAME
gzip /tmp/pg_backup.dump

# Encrypt the gzipped backup file
# using GPG passphrase

gpg --yes --batch --passphrase=$PG_BACKUP_PASSWORD -c /tmp/pg_backup.dump.gz

# Remove the plaintext backup file

rm /tmp/pg_backup.dump.gz

# Generate backup filename based
# on the current date

BACKUP_FILE_NAME="mechanical-meat-database-backup-$(date '+%Y-%m-%d_%H.%M').gpg"

# Make sure to use the UTC
# date for S3 signature!

#DATE=`date -R -u`

#S3_PATH="/${S3_BUCKET}/${BACKUP_FILE_NAME}"

# Generate S3 signature needed
# to upload file to the bucket

#S3_STRING="PUT\n\napplication/octet-stream\n${DATE}\n${S3_PATH}"
#S3_SIGNATURE=`echo -en ${S3_STRING} | openssl sha1 -hmac ${S3_SECRET} -binary | base64`

# Upload the file to S3 using
# the signature auth header
#curl -X PUT -T "/tmp/pg_backup.dump.gz.gpg" \
#  -H "Host: ${S3_BUCKET}.s3-us-east-2.amazonaws.com" \
#  -H "Date: ${DATE}" \
#  -H "Content-Type: application/octet-stream" \
#  -H "Authorization: AWS ${S3_KEY}:${S3_SIGNATURE}" \
#  https://${S3_BUCKET}.s3-us-east-2.amazonaws.com/${BACKUP_FILE_NAME}

# rename file
mv /tmp/pg_backup.dump.gz.gpg "${BACKUP_FILE_NAME}"

#fileLocal="${1:-example-local-file.ext}"
fileLocal="${1:-BACKUP_FILE_NAME}"
bucket="${2:-mechanical-meat-database-backup}"
region="${3:-us-east-2}"
storageClass="${4:-STANDARD}"  # or 'REDUCED_REDUNDANCY'

m_openssl() {
  if [ -f /usr/local/opt/openssl@1.1/bin/openssl ]; then
    /usr/local/opt/openssl@1.1/bin/openssl "$@"
  elif [ -f /usr/local/opt/openssl/bin/openssl ]; then
    /usr/local/opt/openssl/bin/openssl "$@"
  else
    openssl "$@"
  fi
}

m_sed() {
  if which gsed > /dev/null 2>&1; then
    gsed "$@"
  else
    sed "$@"
  fi
}

awsStringSign4() {
  kSecret="AWS4$1"
  kDate=$(printf         '%s' "$2" | m_openssl dgst -sha256 -hex -mac HMAC -macopt "key:${kSecret}"     2>/dev/null | m_sed 's/^.* //')
  kRegion=$(printf       '%s' "$3" | m_openssl dgst -sha256 -hex -mac HMAC -macopt "hexkey:${kDate}"    2>/dev/null | m_sed 's/^.* //')
  kService=$(printf      '%s' "$4" | m_openssl dgst -sha256 -hex -mac HMAC -macopt "hexkey:${kRegion}"  2>/dev/null | m_sed 's/^.* //')
  kSigning=$(printf 'aws4_request' | m_openssl dgst -sha256 -hex -mac HMAC -macopt "hexkey:${kService}" 2>/dev/null | m_sed 's/^.* //')
  signedString=$(printf  '%s' "$5" | m_openssl dgst -sha256 -hex -mac HMAC -macopt "hexkey:${kSigning}" 2>/dev/null | m_sed 's/^.* //')
  printf '%s' "${signedString}"
}

iniGet() {
  # based on: https://stackoverflow.com/questions/22550265/read-certain-key-from-certain-section-of-ini-file-sed-awk#comment34321563_22550640
  printf '%s' "$(m_sed -n -E "/\[$2\]/,/\[.*\]/{/$3/s/(.*)=[ \\t]*(.*)/\2/p}" "$1")"
}

# Initialize access keys
if [ -z "${AWS_CONFIG_FILE:-}" ]; then
  if [ -z "${S3_KEY:-}" ]; then
    echo 'AWS_CONFIG_FILE or AWS_ACCESS_KEY/AWS_SECRET_KEY envvars not set.'
    exit 1
  else
    awsAccess="${S3_KEY}"
    awsSecret="${S3_SECRET}"
    awsRegion='us-east-1'
  fi
else
  awsProfile='default'

  # Read standard aws-cli configuration file
  # pointed to by the envvar AWS_CONFIG_FILE
  awsAccess="$(iniGet "${AWS_CONFIG_FILE}" "${awsProfile}" 'aws_access_key_id')"
  awsSecret="$(iniGet "${AWS_CONFIG_FILE}" "${awsProfile}" 'aws_secret_access_key')"
  awsRegion="$(iniGet "${AWS_CONFIG_FILE}" "${awsProfile}" 'region')"
fi

# Initialize defaults
fileRemote="${fileLocal}"

if [ -z "${region}" ]; then
  region="${awsRegion}"
fi

#echo "${awsAccess}"
#echo "${awsSecret}"
echo "Uploading" "${fileLocal}" "->" "${S3_BUCKET}" "${region}" "${storageClass}"
echo "| $(uname) | $(m_openssl version) | $(m_sed --version | head -1) |"

# Initialize helper variables

httpReq='PUT'
authType='AWS4-HMAC-SHA256'
service='s3'
baseUrl=".${service}.amazonaws.com"
dateValueS=$(date -u +'%Y%m%d')
dateValueL=$(date -u +'%Y%m%dT%H%M%SZ')
if hash file 2>/dev/null; then
  contentType="$(file -b --mime-type "${fileLocal}")"
else
  contentType='application/octet-stream'
fi

# 0. Hash the file to be uploaded

if [ -f "${fileLocal}" ]; then
  payloadHash=$(m_openssl dgst -sha256 -hex < "${fileLocal}" 2>/dev/null | m_sed 's/^.* //')
else
  echo "File not found: '${fileLocal}'"
  exit 1
fi

# 1. Create canonical request
# NOTE: order significant in ${headerList} and ${canonicalRequest}
headerList='content-type;host;x-amz-content-sha256;x-amz-date;x-amz-server-side-encryption;x-amz-storage-class'

canonicalRequest="\
${httpReq}
/${fileRemote}

content-type:${contentType}
host:${S3_BUCKET}${baseUrl}
x-amz-content-sha256:${payloadHash}
x-amz-date:${dateValueL}
x-amz-server-side-encryption:AES256
x-amz-storage-class:${storageClass}

${headerList}
${payloadHash}"

# Hash it
canonicalRequestHash=$(printf '%s' "${canonicalRequest}" | m_openssl dgst -sha256 -hex 2>/dev/null | m_sed 's/^.* //')

# 2. Create string to sign
stringToSign="\
${authType}
${dateValueL}
${dateValueS}/${region}/${service}/aws4_request
${canonicalRequestHash}"

# 3. Sign the string
signature=$(awsStringSign4 "${awsSecret}" "${dateValueS}" "${region}" "${service}" "${stringToSign}")

# Upload
curl -s -L --proto-redir =https -X "${httpReq}" -T "${fileLocal}" \
  -H "Content-Type: ${contentType}" \
  -H "Host: ${S3_BUCKET}${baseUrl}" \
  -H "X-Amz-Content-SHA256: ${payloadHash}" \
  -H "X-Amz-Date: ${dateValueL}" \
  -H "X-Amz-Server-Side-Encryption: AES256" \
  -H "X-Amz-Storage-Class: ${storageClass}" \
  -H "Authorization: ${authType} Credential=${awsAccess}/${dateValueS}/${region}/${service}/aws4_request, SignedHeaders=${headerList}, Signature=${signature}" \
  "https://${S3_BUCKET}${baseUrl}/${BACKUP_FILE_NAME}"

# Remove the encrypted backup file
#rm /tmp/pg_backup.dump.gz.gpg
rm "${BACKUP_FILE_NAME}"
