# 使用多階段構建
FROM golang:1.20-alpine AS builder

# 安裝基本工具
RUN apk add --no-cache git build-base

# 設置工作目錄
WORKDIR /app

# 複製 go.mod 和 go.sum
COPY go.mod go.sum ./

# 下載依賴
RUN go mod download

# 複製源代碼
COPY . .

# 構建應用
RUN CGO_ENABLED=0 GOOS=linux go build -o main .

# 最終階段
FROM alpine:latest

# 安裝 FFmpeg 和其他必要工具
RUN apk add --no-cache \
    ffmpeg \
    wget \
    ca-certificates \
    tzdata

# 創建必要的目錄
RUN mkdir -p /app/contents /app/tables /app/data

# 從構建階段複製二進制文件和必要文件
COPY --from=builder /app/main /app/
COPY --from=builder /app/tables/schema.yml /app/tables/
COPY --from=builder /app/api/static /app/api/static

# 設置工作目錄
WORKDIR /app

# 設置環境變量
ENV GIN_MODE=release \
    TZ=Asia/Taipei

# 創建非 root 用戶
RUN adduser -D -H -h /app appuser && \
    chown -R appuser:appuser /app

# 切換到非 root 用戶
USER appuser

# 暴露端口
EXPOSE 8080

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --spider -q http://localhost:8080 || exit 1

# 設置入口點
ENTRYPOINT ["/app/main"] 