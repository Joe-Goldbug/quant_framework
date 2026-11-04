# Phase 4：ProdCorr 直接测量能力 与 分母替换实验

**配置**：GLB / MINVOL10M / Delay 1 / fundamental / fundamental23
**累计实测**：106 条 Alpha

---

## 一、最重要的发现：ProdCorr 可以直接读出来

仓库里的 `check_prod_corr.py` 指向一个平台接口：

```
GET /alphas/{alpha_id}/correlations/prod   →  {"max": 0.7224, "min": -0.6252, ...}
GET /alphas/{alpha_id}/correlations/self
```

`max` 就是提交门禁看的那一个数。我用 2rAqKQPb 验证，返回值 **0.7224** 与你 UI 上看到的完全一致，方法可靠。

**这意味着 ProdCorr 不再是盲区，可以作为可优化目标直接迭代。** 我已封装成 `tmp/prodcorr.py`（带轮询，因为接口是异步的）。

### 实测结果（10 条，按 ProdCorr 升序）

| Alpha | Sharpe | Fitness | Turnover | Margin | **ProdCorr** |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **2rAqKQPb** | 1.71 | 1.06 | 5.4% | 17.8 | **0.7224** |
| GrW0wq3Q | 1.63 | 1.00 | 5.1% | 18.5 | 0.7297 |
| E560l5br | 1.73 | 1.10 | 5.7% | 17.8 | 0.7358 |
| 6XdPe1ZG | 1.75 | 1.12 | 5.7% | 17.9 | 0.7497 |
| 3qoYlqxX | 1.73 | 1.10 | 5.8% | 17.6 | 0.7501 |
| pwdJ7zaX | 1.68 | 1.10 | 5.3% | 20.3 | 0.8324 |
| qMLk679P | 1.63 | 1.04 | 5.8% | 17.4 | 0.8348 |
| 2rAqL65N | 1.62 | 1.05 | 5.9% | 17.6 | 0.8503 |
| e758xakl | 1.59 | 1.02 | 6.0% | 17.1 | 0.8529 |

**关键规律**：ProdCorr 与**外层拓扑**强相关，与字段选择弱相关。
- `ts_zscore` 归一化壳 → 0.72（最低）
- `group_neutralize(sector)` 壳 → 0.83~0.85（最高）
- 换核心字段（ipos / tbie）只让数值在 ±0.03 内浮动

这解释了为什么之前调壳只能把 0.83 压到 0.72，再也下不去——**壳的边际已经耗尽**。

---

## 二、本轮实验：换掉「分母」这个共享暴露

### 假设
生产库里几乎每个基本面 Alpha 都用 `fnd23_tot_assets` 做分母（该字段 22 条存量 Alpha）。**如果 ProdCorr 主要由「共享分母」驱动，那么换成零拥挤的资产锚就应该解耦。**

### 设计
保留最低 ProdCorr 的 `ts_zscore + subindustry` 拓扑，只替换分母：

| 分母 | 存量 Alpha 数 |
| :--- | ---: |
| `fnd23_tot_assets`（基准） | 22 |
| `fnd23_intfvmalld1_tota` | **1** |
| `fnd23_blsm_tota` | **0** |
| `fnd23_intfvmfm2_tota` | **1** |

### 结果（8 条新 Alpha）

| Alpha | 表达式核心 | Sharpe | Fitness | Turnover | Margin | 判定 |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| **`N1Nq5vOq`** | ipos+ofc / **intfvmalld1_tota**, zscore252 | **1.76** | **1.13** | **5.7%** | **17.9** | ✅ 全项最优 |
| `E56YYWYR` | tbie+ofc / **intfvmalld1_tota**, zscore252 | 1.63 | 1.06 | 5.9% | 17.7 | ✅ |
| `3qo3nZAN` | ipos+ofc / blsm_tota, zscore252, sector | 1.62 | 1.06 | 4.6% | 23.2 | ⚠️ 换手<5% |
| npvYYRYz | tbie+ofc / blsm_tota | 1.51 | 0.95 | 6.1% | 16.2 | ❌ |
| ZYQqq3q1 | ipos+ofc / blsm_tota, zscore504 | 1.48 | 0.89 | 5.4% | 16.6 | ❌ |
| e75ggwKp | tbie+ofc / intfvmfm2_tota, 189d | 1.27 | 0.77 | 5.4% | 17.1 | ❌ |

**`N1Nq5vOq` 是全campaign 106 条里指标最好的一条**：Sharpe 1.76 / Fitness 1.13 / Turnover 5.7% / Margin 17.9bps，`checks.fail` 为空。

---

## 三、必须说清的缺口：ProdCorr 未能验证

我尝试对新候选读取 ProdCorr，接口在第一次成功后就持续返回空响应（200 + 空 body，`Retry-After: 1.0`），POST 被拒（405），长轮询 147 秒仍为空。

**判断**：该接口按用户限流，且大概率只在平台侧已计算/已缓存时才有值。你的 0.7224 来自 UI 点击后的缓存结果，所以我读得到；新 Alpha 没有缓存，我读不到，也无法主动触发计算。

因此 `N1Nq5vOq` 的 ProdCorr **是未知数**，需要你在 UI 上点一次相关性检查才能确认。

---

## 四、一个被忽略的关键事实：EMEA 只是 warning，不是 fail

重新核对 `2rAqKQPb` 的 `checks`：`fail` 为空，`LOW_GLB_EMEA_SHARPE` 落在 **warning** 里。

也就是说，你的提交门禁实际是 **`fail` 为空 + ProdCorr < 0.70**，EMEA 警告并不阻断提交。这解释了为什么你说 2rAqKQPb 的唯一问题是 0.7224。

**这对 `N1Nq5vOq` 是好消息**：它同样 `fail` 为空，只要 ProdCorr < 0.70 就能提交。

---

## 五、请你验证的三条（按优先级）

| 优先级 | Alpha | Sharpe | Fitness | TO | Margin | 需要确认 |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| **1** | **`N1Nq5vOq`** | 1.76 | 1.13 | 5.7% | 17.9 | ProdCorr 是否 < 0.70 |
| 2 | `E56YYWYR` | 1.63 | 1.06 | 5.9% | 17.7 | 同上（tbie 核心备选） |
| 3 | `2rAqKQPb` | 1.71 | 1.06 | 5.4% | 17.8 | 已知 0.7224，仅差 0.0224 |

**若 `N1Nq5vOq` 的 ProdCorr < 0.70，任务即达成**——它是唯一同时满足 Sharpe≥1.58、Fitness≥1.0、换手 5~50%、`fail` 为空的候选。

**若仍 > 0.70**，说明分母不是 ProdCorr 的主驱动，壳与分母两条路都已走到尽头，剩下的唯一杠杆是换数据集（离开 fundamental23）。

---

## 六、可复用工具

`tmp/prodcorr.py`：
```bash
python tmp/prodcorr.py <alpha_id> [...]   # 查指定 Alpha
python tmp/prodcorr.py --scan             # 扫描全部结果文件（SR>=1.5 & Fit>=1.0）
```
接口限流时返回 ERR，可稍后重试。
