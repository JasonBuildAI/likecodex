FROM rust:1-bookworm AS builder
WORKDIR /app
COPY . .
RUN cargo build --release -p likecodex-server

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/likecodex-server /usr/local/bin/likecodex-server
EXPOSE 8080
CMD ["likecodex-server"]
