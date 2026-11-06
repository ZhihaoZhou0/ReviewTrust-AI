# A1 清洗规则与 PostgreSQL 数据契约

本契约基于 DataHive 数据集的固定版本 `2531d9083bd3aab11261eab7e69d0d0f358a6d6f`。原始数据审计见 [data-audit.md](data-audit.md)，本次清洗计数见 [cleaning-report.json](cleaning-report.json)。

## 运行清洗

从仓库根目录执行：

```bash
python3 pipeline/clean_dataset.py \
  --products data/raw/products.csv \
  --reviews data/raw/reviews.csv \
  --output-dir data/processed \
  --report docs/cleaning-report.json
```

输出是 `data/processed/products_clean.csv` 和 `data/processed/reviews_clean.csv`。两份原始 CSV 不会被修改；`data/processed/` 已被 Git 忽略。`source_row_number` 是原 CSV 中从 1 开始的数据记录序号，不是物理行号，因为正文可能换行。`source_row_hash` 是按原始 CSV 字段顺序计算的 SHA-256，用于识别完全相同的源记录；它不表示评论真假。

本版结果：2,727 个商品全部保留；255,966 条原始评论中移除 3,832 条所有 CSV 字段相同的重复记录，输出 252,134 条。没有其他记录被拒绝。清洗脚本若遇到必填字段缺失、值越界、无法解析的日期或 JSON、孤立 `asin`，会在报告中记录拒绝原因和数量。

## 字段及规则

| 来源 | 数据库字段 | 规则 |
| --- | --- | --- |
| `products.asin` | `reviewtrust.products.asin` | 大写、10 位字母数字；商品主键 |
| `products.title` | `title` | 必填，去首尾空白 |
| `products.rating` | `source_rating` | 商品页展示评分，1–5；与样本评论均分不同 |
| `products.number_of_ratings` | `source_rating_count` | 商品页展示评分数量；与样本行数不同 |
| `products.breadcrumbs` | `category_breadcrumbs` | 可空；保留原分类路径 |
| `products.alt_images`, `characteristics` | 同名 `jsonb` | 分别验证为 JSON 数组、JSON 对象 |
| `reviews.id` | `source_review_id` | 必填但不唯一；不能作主键 |
| `reviews.asin` | `asin` | 必须能关联到 `products.asin` |
| `reviews.body` | `body` | 保留非空原文；空白正文存 NULL，不因空正文删除评分 |
| `reviews.date` | `review_date` | 解析源格式，存 PostgreSQL `date` |
| `reviews.stars` | `stars` | 1–5 的整数 |
| `reviews.verified_purchase` | `verified_purchase` | `1`/`true` 为 TRUE，`0`/`false` 为 FALSE，空值为 NULL；NULL 不是 FALSE |
| `reviews.found_helpful` | `found_helpful` | 非负整数 |
| `reviews.images`, `videos` | 同名 `jsonb` | 验证为 JSON 数组 |
| `reviews.variation` | `variation` | 普通文本；源值不是 JSON |

其余 URL、标题、描述、用户 ID 保留为可空文本。评论表使用内部 `review_pk` 主键；`source_row_hash` 唯一，`(asin, source_review_id)` 不加唯一约束，因为源文件中确有 10 条该组合相同但内容不同的评论。`loaded_at` 是入库时间，不是评论发表时间。建表定义见 [schema.sql](../database/schema.sql)。

## 给下游的查询口径

```sql
-- 样本评分：只用本次导入且去除完全重复行的评论。
SELECT p.asin, p.title, p.source_rating, p.source_rating_count,
       count(r.review_pk) AS sample_review_count,
       round(avg(r.stars), 2) AS sample_rating
FROM reviewtrust.products AS p
LEFT JOIN reviewtrust.reviews AS r ON r.asin = p.asin
GROUP BY p.asin;
```

- B 组：对文本相似度和 Pros & Cons 使用 `body IS NOT NULL` 的评论；做评分统计时可包含空正文但有合法星级的评论。不要把 `verified_purchase IS NULL` 当成未验证购买。
- C/D 组：页面需分别标注 `source_rating`（商品页评分）与基于 CSV 子集的 `sample_rating`。数据日期范围为 1999-07-12 至 2025-07-17，且大多数商品只有最多 100 条评论样本。
- A2：可使用 `source_row_hash` 识别重复来源记录；未来版本应另行记录批次和版本，不把 `source_row_number` 当成跨版本稳定 ID。

## 已完成验证

使用临时 PostgreSQL 16 容器执行 [schema.sql](../database/schema.sql) 并导入两份清洗后 CSV：商品 2,727 行、评论 252,134 行；外键、`jsonb`、日期、布尔值、检查约束全部通过。导入后有 206 条空正文、2,395 条购买验证状态未知；同一 `(asin, source_review_id)` 但内容不同的额外行有 10 条。临时容器已移除。
