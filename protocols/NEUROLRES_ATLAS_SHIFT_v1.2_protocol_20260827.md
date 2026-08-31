# NEUROLRES-ATLAS-SHIFT v1.2 冻结协议

## 1. 协议身份与形成原因

- 协议标识：`NEUROLRES-ATLAS-SHIFT-v1.2`
- 冻结日期：2026-08-27（Asia/Shanghai）
- 目标期刊：*Neurological Research*
- 文章类型：Original Research Article
- 状态：`FROZEN_AFTER_V1.1_RESOURCE_STOP_BEFORE_ANY_V1.2_PREDICTION`
- 建议题名：**Temporal and source robustness of a resource-efficient five-fold stroke-lesion segmentation ensemble: multicenter external evaluation with a single-source stress test**

v1.2 是独立于 v1.1 的新协议。v1.1 的正式推理因仓库默认五折 TTA 在当前 CPU 上预计需要约 502.4 小时而停止；其正式输出数为 0，G3–G5 均未运行。v1.1 的所有协议、pilot、G0–G2、权重和停止记录永久保留，不得覆盖或改名为 v1.2。

v1.2 在形成前已经看过 v1.1 Pilot-36 的描述性模型表现。为避免把已观察病例当作新的正式证据，Pilot-36 的 36 例永久排除出 v1.2 的主要和次要效果分析，只允许其中一例用于不读取 GT、不计算指标的执行烟雾测试。

## 2. 固定研究问题

主要问题保持为：冻结的 2022 ATLAS R2 分割模型在时间/来源更新后的多中心 R3_NEW 队列上，病灶检出表现是否相对 R2_TEST 出现有意义下降？SOOP 仍仅作为一个可识别来源的描述性压力测试。

v1.2 只改变推理资源合同：保留五折等权概率平均，但关闭 test-time augmentation（TTA）。不得把 v1.2 写成 v1.1 仓库默认推理的复现；手稿必须明确报告无 TTA。

## 3. 数据合同与独立性

唯一数据来源仍为授权的 ATLAS R3.0 RAW/native-space 发布包。v1.1 G0–G2 已在任何正式模型输出前通过，其固定证据哈希由 v1.2 冻结清单继承。

原始效果层分母为 R2_TEST 300、SOOP 169、R3_NEW 329。排除固定 Pilot-36（每层 12 例）后，v1.2 正式分母为：

| 层 | v1.2 正式分母 | 角色 |
|---|---:|---|
| `R2_TEST` | 288 | 多中心时间邻近参照层 |
| `SOOP` | 157 | 单来源描述性压力测试 |
| `R3_NEW` | 317 | 多中心时间/来源外部层 |
| 合计 | 762 | 固定正式效果分母 |

排除集合唯一来源为哈希已锁定的 v1.1 Pilot-36 manifest。不得因影像、病灶、中心、失败或模型表现增删病例。独立单位为 case；失败病例保留在固定分母中。

## 4. 冻结模型与推理合同

模型权重与 v1.1 完全相同：MAPPING 2022 ATLAS R2 challenge 默认 nnU-Net，仓库 commit `465ec87689d004c175b47b6dec3240ea9378348e`，task `Task100_ATLAS_v2`，trainer `nnUNetTrainerV2__nnUNetPlansv2.1`，checkpoint `model_final_checkpoint`。

正式推理固定为：

- fold 0、1、2、3、4；
- 每个 fold 输出 softmax 概率，五折按等权算术平均；
- `--disable_tta`；
- `--disable_mixed_precision`；
- 保存 NIfTI、NPZ 和 properties PKL；
- nnU-Net 默认滑窗、步长、Gaussian weighting 和阈值；
- 无自定义后处理；
- 禁止换 fold、选择表现较好 fold、调阈值、用 GT 裁剪、重采样 GT 或依据结果改变参数。

关闭 TTA 是 v1.2 在首次预测前明示的资源约束，不是看到正式结果后的补救分析。

## 5. 不评分烟雾测试

正式运行前只允许一次烟雾测试：从已观察的 v1.1 Pilot-36 中按 T1 压缩文件字节数最接近 Pilot-36 中位数选择 token；固定为 `v11p010`。选择不依赖病灶或模型表现。

烟雾测试使用五折等权概率平均、关闭 TTA、关闭混合精度。不得打开其 GT、不得计算 Dice、lesion-F1、PR-AUC、体积误差或任何效果指标。

烟雾测试通过门：

- 五个冻结 checkpoint 和 plans 哈希通过；
- 输入可读且不被改写；
- NIfTI/NPZ/PKL 三件套各 1；
- 输出有限、概率范围及和约束合法、预测与原 T1 空间一致；
- 无 OOM、崩溃或中断；
- 当前可用磁盘至少 20 GB；
- 冻结规划估计 `34/36 × 762 × 5 / 60 = 59.97` 小时，不超过 72 小时。

任一失败则停止 v1.2 正式推理。只允许在同一烟雾病例上修复无结果信息的 I/O/环境问题并保留失败记录；分析参数不得改变。

## 6. 主要终点与统计分析

主要终点仍为按中心宏平均的 lesion-wise F1。唯一主要对比仍为 `R2_TEST - R3_NEW`。case 级病灶匹配采用 v1.1 已锁定的 ISLES'26 官方定义；中心内 case 等权平均，层内中心等权平均。

对两个层的中心标签并集进行联合 cluster bootstrap，10,000 次，种子 `260827`。每次从中心并集有放回抽取同等数量中心；同一中心若在两层均存在，则两层病例同时进入该重复。报告 percentile 95% CI 和双侧 bootstrap p 值。只有一个主要对比，不作多重性校正。

SOOP 只报告 case 级描述性指标、分布、失败率和条件于该单一来源的 case bootstrap 95% CI，不进入中心级主要对比，不主张跨中心泛化。

共同次要终点保持为 Dice、绝对体积差、绝对病灶数差、soft-map PR-AUC、空预测率和推理失败率。亚组与 v1.1 相同；不得从 pilot 或正式结果中新增亚组。

## 7. 正式门控与失败动作

- **G0–G2**：继承并重新核对 v1.1 在正式模型输出前通过的 archive、分母、泄漏和模型来源证据；v1.2 762 例映射必须精确等于全量效果队列减去固定 Pilot-36。
- **G3**：R2_TEST、SOOP、R3_NEW 每层推理成功率均至少 95%。
- **G4**：仅当 `R2_TEST - R3_NEW >= 0.05`、95% CI 下界大于 0 且双侧 p<0.05，才允许主张有意义的多中心时间/来源移位下降。
- **G5**：G0–G3 通过但 G4 失败时，只能定位为阴性外部验证/稳健性研究，不得救结果。

不得把 Pilot-36 并回正式分母，不得扩大样本、删失败病例、伪拆 SOOP 中心、换模型、改阈值或增加结果驱动分析。关联、分割性能和失败模式不得写成临床结局、机制证明、临床部署或优于医师。

## 8. 计算与隐私

正式运行在当前本地 CPU 上执行，使用 `caffeinate` 防止空闲休眠；合盖仍可能暂停。运行脚本必须支持保留已完成输出并在中断后跳过完整病例。原始数据、token 映射、预测和 case 级指标只保存在 `data/authorized/atlas_r3/formal_v1.2/`，不得提交或重新分发。

正式推理完成前不得运行 G4–G5。v1.2 的结果不得与 v1.1 pilot 合并，也不得声称复现了 v1.1 的 TTA 默认设置。
