# 项目开发与运行规范 (GEMINI.md)

## 项目常见避坑与错误记录

### 1. 云端容器（Google Colab）内存与虚拟内存限制
- **错误现象**：在 Google Colab 免费 T4 实例运行大模型加载时，出现 `Your session crashed after using all available RAM`，即使尝试通过 `fallocate` / `mkswap` / `swapon` 挂载 10GB 虚拟内存，依然无效并报错或被 OOM 强杀。
- **根本原因**：
  1. Colab 运行在非特权 Docker 容器内，Linux 内核安全机制禁止普通容器执行 `swapon`（报错 `Operation not permitted`）；
  2. Colab 后台守护进程直接依据 Linux cgroups 物理内存上限（免费版约 12.7GB）进行强制监控与杀死进程，完全无视外部虚拟内存。
  3. 类似 CogVideoX-5B、Wan 2.1 等参数量 >5B 的工业级视频模型在反序列化加载时，瞬时内存容易飙升至 14GB~20GB+。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁在 Colab 免费容器中尝试创建 Swapfile 试图扩容内存，纯属徒劳；
  - **DON'T**：严禁在 12GB 物理内存环境下直接加载未量化的大型视频模型完整权重；
  - **DO**：针对 AI 短剧/漫剧工业化生产，建议租赁独立算力平台（如 AutoDL 的 RTX 4090 24GB 物理单卡），彻底摆脱平台 RAM 瓶颈与 Docker 特权限制；
  - **DO**：加载大型扩散模型时必须严格开启 `low_cpu_mem_usage=True` 并使用 FP16/BF16 精度。

### 2. 生图自动化流水线“重吞吐、轻质检”与提示词污染缺陷
- **错误现象**：在全自动批量调用图像扩散模型（如 Flux.1-dev）时，盲目追求大吞吐量连续跑完数集（上百张图），仅以文件下载成功和体积大小作为判据，未在运行过程中实时接入多模态视觉质检与语义对齐审查。导致为了防塑料感而设置的人像通用词（如 `human facial skin`, `human gaze`）发生“提示词污染”，使道具特写与场景全景镜头全部被强行生成为人脸肖像，缺陷被放大至全剧 119 个镜头。
- **根本原因**：
  1. **执行惯性与片面追求速度**：急于在用户规定时间内交付全量镜头，将“程序无报错、出图数量达标”误当作“生成质量达标”；
  2. **抽样检查存在严重幸存者偏差**：在流水线启动初期仅抽检了前 2 个纯人物特写镜头，见人像质感惊艳便盲目自信，未对道具镜头和场景镜头进行交叉抽样；
  3. **缺乏流水线前置熔断卡点机制**：没有在生成脚本中设计“初期各类型各跑 1 张并强制执行视觉多模态语义验收（契合度 <85% 则立即熔断暂停）”的保护逻辑。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁在未经过【人物】、【道具】、【场景】三类代表镜头的交叉多模态视觉验收前，开启无人值守的全量连续生图；
  - **DON'T**：严禁将强特征的人像面部皮肤词（`facial skin`, `human eyes`, `gaze`）作为全局通用提示词前缀，必须按镜头类型进行严格的【三分类提示词解耦】；
  - **DO**：生图流水线必须内置“前置熔断卡点”：正式批量生产前，先跑 3 个不同类型的基准镜头，由视觉模型即时评分打分，合格率 ≥85% 方可放行后续批量任务；
  - **DO**：在任务执行过程中必须秉持实事求是的工程师原则，实时跟进质量验收，发现偏离立即主动阻断，绝不放任缺陷扩散。

### 3. Flux.1-dev 中式审美锁脸与防塑料感参数调优规范
- **错误现象**：生图出现磨皮塑料感、背景大光圈假虚化，或东方人物面孔出现欧美混血化/西方骨相。
- **根本原因**：
  1. FluxGuidance 设置过高（≥3.0）会导致画面边缘过度收紧、皮肤被算法抹去天然微小瑕疵，形成塑料娃娃质感；
  2. 在正向提示词中写入类似 `Negative constraint: caucasian, western face` 的语句时，T5 文本编码器不具备否定词过滤逻辑，反而会把 `caucasian` 等词作为注意力语义目标召回，导致人脸西化；
  3. 默认 euler + simple 采样组合在大步数下容易产生过度平滑的数字光斑与浅景深虚化。
- **正确做法与约束（Dos & Don'ts）**：
  - **DO**：将 FluxGuidance 锁定在 `2.0 - 2.3`（推荐 2.2），采样器更换为 `deis` + `beta` 调度器，30 步；
  - **DO**：在正向提示词末尾固定追加无括号权重的 T5 胶片电影级自然语言后缀：`, cinematic 35mm film photography, authentic film grain, deep focus with natural optical depth, sharp environment details without artificial bokeh, realistic skin pores, subtle imperfections, authentic contemporary Chinese drama aesthetic, completely natural lighting, raw photography.`；
  - **DON'T**：严禁在正向提示词中书写任何负面词或否定句式，必须采用纯正面东方特征词（`pure East Asian features`, `handsome Chinese male`, `Chinese drama aesthetic`）引导；
  - **DO**：主要人物必须先生成多角度（正面、45度侧颜、特写眼神）定妆锚点图，并经多模态视觉质检确认后再作为故事板分镜锁脸参考。

### 4. 角色一致性必须以已验收定妆锚点图执行图生图（Img2Img / 垫图锁脸）
- **错误现象**：在分镜批量生成时，误以为只要提示词固定了人像细节并固定随机种子，就能保证人脸一致，结果生成出的人物五官骨相每张都不一样。
- **根本原因**：纯文生图（EmptyLatent）从空白高斯噪声开始扩散，只要机位（景别）、环境光照描述稍有变化，扩散模型的去噪轨迹就会发散，重新脑补生成一张全新的人脸；文字不变量只能约束风格属性（是否有眼镜、什么发型），根本无法锁死具体的五官骨相与面孔身份。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁在主角分镜生成中仅使用纯文生图（EmptyLatent）试图维持人脸一致性；
  - **DO**：必须严格遵循 `character-refs` skill 的核心原则——以已通过质检验收的定妆图为唯一根底模；
  - **DO**：在 ComfyUI 工作流中通过 `LoadImage` 加载角色锚点图，经过 `VAEEncode` 得到带真实面孔骨相的潜空间底模，`KSampler` 的 `denoise` 设置在 `0.65 ~ 0.72` 之间，兼顾镜头动作变化与面部特征 100% 绝对一致！


### 5. 分镜生成“油光满面”与“低Denoise垫图+固定Seed导致千图一姿”严重事故
- **错误现象**：
  1. 生成的人脸额头、鼻梁、脸颊大面积油光反光，犹如抹了猪油或满头大汗，质感粗劣油腻，沦为废片；
  2. 连续多个镜头的人物姿势、手持道具角度、构图机位完全一模一样，如同连环静态复制粘贴，剧本中的动作全部失效。
- **根本原因**：
  1. **油光反光的物理机理**：正向提示词中写了 `subtle imperfections, realistic skin pores` 等词，在定向光照下被扩散模型的注意力机制错误解析为皮肤油脂反光（Sebum/Oily glare），且缺少明确的“控油（non-greasy, non-oily）”与“哑光（matte skin）”修饰约束；
  2. **分镜千图一姿的算法机理**：在批量脚本中为了追求一致性锁死同一个 `seed`，且使用正面立正半身图做低 `denoise` 垫图，导致原始画面的骨架布局死死固化。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁在主角分镜批量生产中使用固定 Seed，每个分镜必须拥有独立的动态随机种子（如 `seed = base_seed + shot_index * 137`）；
  - **DON'T**：严禁在人物质感提示词中使用可能诱导油光的描述，禁止未受控的强对比顶光；
  - **DO**：必须全面启用清爽控油哑光词汇：`matte natural healthy skin tone, clean handsome features, soft clean diffuse studio daylight, non-greasy, non-oily, clear complexion, authentic contemporary Chinese drama aesthetic`。

### 6. Flux 潜空间图生图局限与全面转入通义千问（Qwen-Image-Edit）原生多模态架构
- **错误现象**：在 Flux.1-dev 中尝试通过 `VAEEncode` 垫图锁脸时陷入不可调和的矛盾：`denoise < 0.70` 则人物动作姿势僵死（千图一姿），`denoise > 0.75` 则五官骨相漂移失控。
- **根本原因**：Flux 没有原生类似 IP-Adapter 或 CLIP Vision 的多模态视觉注入交叉注意力层，强行用全图像素潜空间混合会导致背景、肢体与面部绑定在一起。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁在短剧工业化批量分镜中继续使用暴力全图潜空间融合（Img2Img `denoise 0.68`）；
  - **DO**：全面升级至通义千问 `Qwen-Image-Edit`（基于 `TextEncodeQwenImageEditPlus` 节点）；
  - **DO**：将角色唯一官方定妆母版（`master_id/<char_id>.png`）作为多模态视觉提示传入 Qwen3-VL 8B，配合 `EmptySD3LatentImage` 与 `denoise: 1.0`，实现身体动作 100% 自由调度与面部五官身份骨相的精准锁定。

### 7. 算家云（Suanjiayun）镜像“死软链接”避坑与 0 成本存储持久化规范
- **错误现象**：在算家云租用 ComfyUI 镜像后，发现 `models` 目录下虽然列有大量模型名字，但全部无法加载，启动报错 `Value not in list: unet_name ... invalid prompt`，终端查看发现所有模型文件全是指向 `/root/sj-data/LargeModel/...` 的死软链接（Broken Symlink）。
- **根本原因**：
  1. 算家云平台为减小镜像分发体积对镜像进行了“动静剥离”，将环境与大模型解耦；镜像作者制作时将其私有数据路径 `/root/sj-data` 写死在软链接中，而用户开机时该挂载点为空；
  2. 用户若盲目扩容收费数据盘或开通 `sj-fs` 网盘，关机后每天仍会被持续扣除高额硬盘租金，且关机超 7 天还面临被平台自动释放的风险。
- **正确做法与约束（Dos & Don'ts）**：
  - **DON'T**：严禁花冤枉钱在控制台手动扩容付费数据盘；
  - **DO**：严格认清算家云磁盘生命周期规则：
    - **系统盘 `/`（30GB）**：点击平台「保存镜像」时会**完整打包保存**；
    - **临时盘 `/root/sj-tmp`（50GB）**：读写速度极快，但**保存镜像时会被自动忽略**！
  - **DO**：针对 AI 短剧工业化工作流，核心模型（`qwen_image_2.1_int8_convrot.safetensors` 6.9GB + `qwen3vl_8b_int8_convrot.safetensors` 8.9GB + `qwen_image_2.1_vae_bf16.safetensors` 645MB，总共约 16.5GB）应直接下载存放在**系统盘** `/ComfyUI/models/` 对应子目录中（系统盘 30GB 空间完全充裕）；
  - **DO**：下载完成后，在控制台点击**「保存镜像」**，将其固化至算家云赠送的 **50GB 免费项目镜像库**中；随后直接**释放（销毁）**实例，彻底实现**0 关机存储费、永久云端保存、下次开机 0 秒即用大模型**。

