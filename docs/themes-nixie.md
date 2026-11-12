# NIXIE RACK 主题：真机定稿

![NIXIE RACK 真机定稿](verification/nixie/nixie-rack-final.png)

## 设计结论

最终方案采用美式机架计数器，而不是把橙色发光字体直接放在黑色背景上：

- 三支真实冷阴极辉光管显示 7 天剩余额度，固定为三位并保留前导零。
- 玻璃顶部排气嘴、阳极网、未点亮阴极堆栈、云母支架、管座和管脚均保留在静态层。
- 点亮阴极使用十枚独立 ARGB8888 精灵，运行时额外叠加宽范围琥珀辉光，使阳极网、玻璃肩部和管座共同被照亮。
- 黑色阳极氧化铝、烟熏窗口和低亮刻字压低环境亮度，让辉光管保持唯一主视觉。
- Today、7 Days、RESET、任务与电量均使用适合约 4cm 屏幕的大字号，不依赖难以辨认的微型说明文字。

## 动态信息与滚轮

- `TODAY < 100M` 时保留小数滚轮，例如 `96.2M`。
- `TODAY = 100M–999M` 时切换为三枚 39px 等宽整数滚轮和一枚等宽单位滚轮，不留下空的小数槽。
- Today 与 7 Days 的数字均按滚轮几何中心定位；完成 `0–9` 真机逐字扫描，并对 D-DIN 的 `7` 进行 1px 光学校正，最终中心误差不超过 0.5px。
- Today 与 7 Days 均支持三位数字、一枚独立窄小数滚轮和一枚单位滚轮；无小数时使用三位整数滚轮。7 Days 复用 Today 的 39px 数字格、12px 小数格和单位格纹理，小数格可位于第一位或第二位数字之后，完整显示 `1.03B`、`12.3B`、`96.2M`；整数 `347M` 保持原布局。7 Days 从原始 Token 数四舍五入到三位有效数字，处理 `9.995B → 10.0B`、`99.95B → 100B`、`999.99B → 1.00T`，禁止截掉高位。
- RESET 的 `D` / `H` 使用较小字号并与数值底部对齐；任务数保持两位动态显示。
- 电量来自 AXP2101 的真实 PMU 读数，以三枚等宽、水平和垂直居中的格子表达，并保留数值百分比。

## 资源分层

- `nixie_bg.rgb565`：480×480 RGB565 静态机架、玻璃管和金属结构。
- `nixie_digit_0.argb8888` 至 `nixie_digit_9.argb8888`：90×108 动态阴极与近场辉光。
- `nixie_today_integer.rgb565`：Today 整数模式的四等分滚轮内层。
- LVGL 动态层：主管辉光、Today / 7 Days、单位、RESET、任务、电量与状态灯。7 Days 小数面板通过带 stride 的图片描述符引用现有背景中的 Today 滚轮切片，不增加图片资源文件。

可重复生成命令：

```bash
python3 tools/generate_nixie_digit_assets.py --install design
python3 tools/generate_nixie_background_assets.py --install design
```

## 真机验收

- 完成背景亮度、金属质感、阴极高度与垂直位置、阳极网染色和玻璃环境辉光校准。
- 覆盖 `77.7M`、`96.2M`、`100M`、`777M`、`888M`、真实电量、三格电池、两位任务和 RESET 对齐。
- 完成 128 项宿主回归测试、`waveshare_amoled_216` 固件编译、LittleFS 与固件烧录。
- 2026-10-22：34 项 C++ 用例及固件编译通过；真机验证 [Today `96.2M` 与 7 Days `1.03B` 的窄小数槽](verification/nixie/week-narrow-decimal-1-03b.png)、`12.3B`、`347M`、小数/整数往返切换与 `100B` 进位。最后恢复真实同步用量 `1,049,002,185`，显示为 [`1.05B`](verification/nixie/week-total-narrow-slot.png)。本次只更新固件，未改动资源分区。
- 滚轮切片的 `data_size` 包含完整的 `stride × height`，并在挂载时通过 `lv_draw_buf_from_image` 校验，确保 LVGL 能绘制小滚轮背景。`1.03B`、`12.3B` 和整数切回小数的三张截图中，窄滚轮上部 12×29 检查区域均与 Today 背景切片的 348 个像素完全一致。[放大对照：左 Today，右 7 Days](verification/nixie/week-narrow-decimal-detail.png)。

本主题只扩展 ESP32 展现层与 USB 视觉 QA 命令，没有修改 macOS 用量读取逻辑或 BLE payload。
