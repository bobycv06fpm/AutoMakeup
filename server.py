#!/usr/bin/python
# -*- encoding: utf-8 -*-
from io import BytesIO

import base64
import json
from PIL import Image, ImageFont, ImageDraw
from flask import Flask, request, Response

import faceutils as futils
import makeup

refs, labels = [], []
with open('refs/name.json', 'r') as f:
    entries = json.load(f)
    for entry in entries:
        labels.append(entry['name'])
        with Image.open(f'refs/' + entry['src']) as image:
            _, prep = makeup.preprocess(image)
            refs.append(prep)

app = Flask(__name__)


@app.route('/transfer/', methods = ['POST'])
def transfer():
    data = json.loads(request.get_data().decode())
    model = data.get('model')
    image = data.get('file') # base64
    image = futils.fpp.beautify(image) # base64
    image = futils.fpp.decode(data.get('file'))
    box, prep = makeup.preprocess(image)
    result = makeup.solver.test(*prep, *refs[model])
    result = futils.merge(image, result, box)
    return futils.fpp.encode(result)


@app.route('/exchange/', methods=['POST'])
def exchange():
    data = json.loads(request.get_data().decode())
    images = [futils.fpp.decode(image) for image in data]
    boxes, preps = [], []
    for image in images:
        box, prep = makeup.preprocess(image)
        boxes.append(box)
        preps.append(prep)
    results = [makeup.solver.test(*preps[0], *preps[1]), 
              makeup.solver.test(*preps[1], *preps[0])]
    for i in range(2):
        # results[i] = futils.fpp.beautify(results[i]) # base64
        # results[i] = futils.fpp.decode(results[i])
        results[i] = futils.merge(images[i], results[i], boxes[i])
        results[i] = futils.fpp.encode(results[i])
    return json.dumps(results)


bg = Image.open('assets/test_result.png')
font_num = ImageFont.truetype('assets/font.otf', 200)
font_label = ImageFont.truetype('assets/font.otf', 140)


@app.route('/test/', methods=['POST'])
def test():
    image = json.loads(request.get_data().decode()).get('file') # base64
    image = futils.fpp.beautify(image) # base64
    src_score = futils.fpp.rank(image)
    image = futils.fpp.decode(image)
    _, prep = makeup.preprocess(image)
    
    model_id = -1
    max_score = src_score
    result = image
    for i, model in enumerate(refs):
        temp = makeup.solver.test(*prep, *model)
        score = futils.fpp.rank(temp)
        if score > max_score:
            model_id = i
            max_score = score
            result = temp
    score = (max_score - src_score) / (100 - src_score) * 39
    score = int(score) + 60

    # draw result image
    result = result.resize((1016, 1016), Image.ANTIALIAS)
    canvas = Image.new(size=bg.size, mode='RGBA', color=(255, 255, 255))
    canvas.paste(result, box=(392, 582))
    canvas.paste(bg, mask=bg)

    grade = 0 if score < 60 else \
            1 if 60 <= score < 70 else \
            2 if 70 <= score < 80 else \
            3 if 80 <= score < 90 else \
            4
    with Image.open(f'assets/{ grade }.png') as remark:
        canvas.paste(remark, mask=remark)

    draw = ImageDraw.Draw(canvas)
    if model_id == -1:
        score = '∞'
        label = "绝美素颜"
    else:
        score = str(score) + '%'
        label = labels[model_id]
    draw.text((88, 162), score, font=font_num, fill='#ffffff')
    for i, c in enumerate(label):
        draw.text((119, 655 + i * 153), c, font=font_label, fill='#ff9181')
        draw.text((110, 647 + i * 153), c, font=font_label, fill='#ffffff')
    return futils.fpp.encode(canvas)


if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 5001, debug = True, ssl_context = ('ssl/server.crt', 'ssl/server.key'))
    # src = Image.open('refs/0.png').convert('RGB')
    # ref = Image.open('refs/2.png').convert('RGB')
    # result = makeup.solver.test(*(makeup.preprocess(src)), *(makeup.preprocess(ref)))
    # result.save('result.png')
