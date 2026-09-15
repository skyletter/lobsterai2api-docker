# 主服务镜像：构建自官方上游源码 lobsterai2api（Go，零外部依赖）
# 由 GitHub Actions 每天跟随官方仓库自动重建并推送至 GHCR
FROM golang:1.23-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/lobsterai2api ./cmd/server \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/login ./cmd/login \
 && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/credit ./cmd/credit

FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata && adduser -D -u 10001 -h /app app
WORKDIR /app
COPY --from=build /out/ /app/
COPY add-account.sh /app/add-account.sh
RUN chmod +x /app/add-account.sh && mkdir -p /app/auths /app/data && chown -R 10001:10001 /app
USER 10001
EXPOSE 8367
ENTRYPOINT ["/app/lobsterai2api", "-config", "/app/config.json"]