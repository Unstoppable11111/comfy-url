import json

wf = json.load(open("/ComfyUI/user/default/workflows/image_qwen_image_2_1_t2i.json"))
for n in wf.get("nodes", []):
    print("mode=%s type=%s id=%s title=%s" % (n.get("mode"), n.get("type"), n.get("id"), n.get("title")))
    if n.get("type") == "CLIPLoader":
        print("     ", n.get("widgets_values"))
