---
name: MHS-AI-Bridge
status: 已完成（v2）
stack: 原生 JavaScript / 零依赖 / 本地编译器
updated: auto
link: https://github.com/Liu-Tangguo/MHS-AI-Bridge
---

一个把大语言模型生成的「架空历史世界状态」编译成 Making History Sandbox（MHS）可直接载入存档的小工具。

- 在线使用（无需安装）：https://liu-tangguo.github.io/MHS-AI-Bridge/converter/convert.html
- 设计要点：AI 只判断「每一块土地归谁」，颜色、regionID、存档结构全部由本地编译；全程离线、零依赖、单文件。
- 数据层覆盖 MHS 底图全部 4,594 个区域，重名/无名区域用稳定 ID 消歧，绝不猜测。
- 端到端测试 50/50 通过；浏览器自检 SELFTEST_OK。
