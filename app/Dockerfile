FROM python:3.11-bookworm

ARG VERSION
ENV VERSION=$VERSION

ARG B_NUM
ENV B_NUM=$B_NUM

ARG BRANCH
ENV BRANCH=$BRANCH

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# I2C + Pillow deps + iproute2 (for IP detection)
RUN apt-get update && apt-get install -y --no-install-recommends \
    i2c-tools python3-smbus iproute2 \
    libjpeg62-turbo zlib1g libfreetype6 libtiff6 libopenjp2-7 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# bring in your code
COPY . .

CMD ["python", "-u", "oled_hello.py"]
