# 本机 TLS 代理测试

`proxy-test-cert.pem` 和 `proxy-test-key.pem` 是专供自动测试使用的公开自签名证书与私钥，域名为 `api.example.com`、`proxy.example.com`，不是用户或服务的真实凭据。请勿用于部署。

`tests/js/network.test.cjs` 将请求经临时回环代理转发到本机 TLS 服务，并仅在需要成功握手的测试中显式信任此证书。生产代码不会加载这些文件，不会关闭证书验证，也不会修改系统证书存储。证书有效期为 2020-01-01 至 2050-01-01；运行测试无需 OpenSSL 或额外 Python/npm 包。
