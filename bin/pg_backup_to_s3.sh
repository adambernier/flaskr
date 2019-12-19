#!/bin/sh

# Set the script to fail fast if there
# is an error or a missing variable

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

DATE=`date -R -u`

S3_PATH="/${S3_BUCKET}/${BACKUP_FILE_NAME}"

# Generate S3 signature needed
# to upload file to the bucket

S3_STRING="PUT\n\napplication/octet-stream\n${DATE}\n${S3_PATH}"
S3_SIGNATURE=`echo -en ${S3_STRING} | openssl sha1 -hmac ${S3_SECRET} -binary | base64`

# Upload the file to S3 using
# the signature auth header

curl -X PUT -T "/tmp/pg_backup.dump.gz.gpg" \
  -H "Host: ${S3_BUCKET}.s3-us-east-2.amazonaws.com" \
  -H "Date: ${DATE}" \
  -H "Content-Type: application/octet-stream" \
  -H "Authorization: AWS ${S3_KEY}:${S3_SIGNATURE}" \
  https://${S3_BUCKET}.s3-us-east-2.amazonaws.com/${BACKUP_FILE_NAME}

# Remove the encrypted backup file

rm /tmp/pg_backup.dump.gz.gpg
