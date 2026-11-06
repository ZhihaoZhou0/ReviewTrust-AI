# DataHive Amazon Reviews 数据审计（A1 · 第 1 步）

## 来源与复现

- 数据集：[datahiveai/Amazon-Reviews-Dataset](https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset)
- 固定版本：`2531d9083bd3aab11261eab7e69d0d0f358a6d6f`
- 原始文件：`products.csv`（15,372,071 字节）、`reviews.csv`（127,363,815 字节）
- 完整统计及 SHA-256：[data-audit.json](data-audit.json)
- 原始文件放在 `data/raw/`，已被 Git 忽略；不要把评论原文提交到仓库。

下载并重新审计：

```bash
mkdir -p data/raw
curl -fL -o data/raw/products.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/products.csv
curl -fL -o data/raw/reviews.csv https://huggingface.co/datasets/datahiveai/Amazon-Reviews-Dataset/resolve/2531d9083bd3aab11261eab7e69d0d0f358a6d6f/reviews.csv
python3 pipeline/audit_dataset.py --products data/raw/products.csv --reviews data/raw/reviews.csv --output docs/data-audit.json
```

## 实际文件结构

| 文件 | 行数 | 原始列 |
| --- | ---: | --- |
| `products.csv` | 2,727 | `url`, `asin`, `main_image`, `alt_images`, `title`, `breadcrumbs`, `rating`, `number_of_ratings`, `description`, `characteristics` |
| `reviews.csv` | 255,966 | `id`, `asin`, `url`, `body`, `date`, `title`, `images`, `videos`, `stars`, `user_id`, `variation`, `found_helpful`, `verified_purchase` |

Hugging Face 默认数据集预览把两份不同结构的 CSV 当作同一个 split，因列冲突报错。应分别读取两个文件，再按 `asin` 关联。数据卡片所列的部分字段名称也不同于实际 CSV；实现以文件表头为准。

## 全量统计

| 检查项 | 结果 |
| --- | ---: |
| 商品 ASIN 唯一值 / 重复 | 2,727 / 0 |
| 评论关联到商品 | 255,966 / 255,966（100%） |
| 无评论商品 | 38 |
| 评论 ID 唯一值 / 重复出现的额外行 | 247,696 / 8,270 |
| 完全相同的评论行（额外行） | 3,832 |
| 同一 `(asin, id)` 重复出现的额外行 | 3,842，其中 10 行内容不同 |
| 空评论正文 | 211 |
| 无法解析的 CSV 行 / 评分 / 日期 | 0 / 0 / 0 |
| 评论日期 | 1999-07-12 至 2025-07-17 |
| 2025 年评论 | 196,119 |
| `verified_purchase` | `1`: 253,543；空值: 2,423；没有 `0` |
| 每个有评论商品的评论数 | 最少 1，中位数 100，最多 100 |
| 恰好 100 条评论的商品 | 2,478 / 2,689 |

商品缺失：`breadcrumbs` 75 行、`description` 3 行。评论缺失：`variation` 43,277 行、`title` 1,333 行、`user_id` 1,333 行、`verified_purchase` 2,423 行、`body` 211 行。评论星级在 1–5 范围内；商品页评分在 1–5 范围内。

## 对 A1、B 组和展示的影响

1. **主键**：`products.asin` 可以作为主键；评论 `id` 及 `(asin, id)` 都不能直接作为唯一键。评论表应采用内部主键，保留 `source_review_id` 和 `asin`。清洗时只移除完全相同的重复行；同键但内容不同的 10 行先保留并记录冲突，避免误删。
2. **评分口径**：2,689 个可比较商品中，2,680 个的商品页 `number_of_ratings` 与 CSV 样本评论数不同。商品页 `rating` 要命名为来源展示评分，样本均分另算，不能把二者混成同一指标。
3. **样本范围**：2,478 个商品恰好各有 100 条评论，明显存在每商品样本上限。评论时间和星级分布不代表该商品全部历史评论。加权评分应明确标为“基于当前样本”。
4. **异常信号**：`verified_purchase` 只有 `1` 或空值，空值不能自动解释为“未验证购买”。B 组不应据此设计二元降权规则。完全相同正文的额外行有 20,549 行，但这只是相同文本，不等于虚假评论。
5. **时间与来源**：这个 DataHive 文件包含 2025 年评论，不能沿用 proposal 中 Amazon Reviews 2023 的数据年份和来源说明。Demo 应显示实际数据集名称和样本日期范围。

## 清洗规则与 Schema

清洗实现、字段映射和数据库交接说明见 [data-contract.md](data-contract.md)。原始 CSV 保留不改，清洗报告记录输入、输出和被移除行数。
