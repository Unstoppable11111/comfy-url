import json

wf = json.load(open("/ComfyUI/user/default/workflows/image_qwen_image_2_1_t2i.json"))
for s in wf.get("definitions", {}).get("subgraphs", []):
    print("== subgraph", s.get("name"))
    for n in s.get("nodes", []):
        print("  mode=%s type=%s id=%s" % (n.get("mode"), n.get("type"), n.get("id")), n.get("widgets_values"))
