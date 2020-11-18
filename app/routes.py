from flask import render_template, redirect, url_for
from app import app
from app.forms import BulForm, CommentForm, TagForm
from pymongo import MongoClient
from bson.objectid import ObjectId
import redis
from collections.abc import MutableMapping
from datetime import datetime


# переменные для хранения подключения к бд и кэшу
client = MongoClient('mongo', 27017)
db = client["mydatabase"]
col = db["bulletins"]
r = redis.Redis(host='redis', port=6379, db=0)
# список всех id дабы не искать по всем ключам редиса
KEYS = []


# функция приводит структуру вида {'a': {'b': 'c'}}
# к виду ключ a:b значение c, чтобы хранить в редиске, и записывает туда
def setflat_skeys(r: redis.Redis, obj: dict, prefix: str, delim: str = ":", *, _autopfix="") -> None:
    allowed_vtypes = (str, bytes, float, int)
    for key, value in obj.items():
        key = _autopfix + key
        if isinstance(value, allowed_vtypes):
            r.set(f"{prefix}{delim}{key}", value)
        elif isinstance(value, MutableMapping):
            setflat_skeys(r, value, prefix, delim, _autopfix=f"{key}{delim}")
        elif isinstance(value, list):
            if len(value) > 0:
                if isinstance(value[0], str):
                    r.sadd(f"{prefix}{delim}{key}", *value)
                elif isinstance(value[0], MutableMapping):
                    for itm in enumerate(value):
                        setflat_skeys(r, itm[1], prefix, delim, _autopfix=f"{key}{delim}{itm[0]}{delim}")
                else:
                    raise TypeError(f"Unsupported value type: {type(value)}")
        else:
            raise TypeError(f"Unsupported value type: {type(value)}")


# функция, достающая из кэша самые простые значения, без вложенности
def fish_out_of_cache_simple(r: redis.Redis, prefix: str, delim: str = ":") -> dict:
    result = {arg: r.get(f'{prefix}{delim}{arg}').decode("utf-8") for arg in ('author', 'title', 'content', 'creation_time')}
    return result


# строку в массив и убрать лишние пробелы
def make_tags(form_data: str):
    return [tag.strip() for tag in form_data.split(',')]


# при запуске программы перебираем базу и все кладем в кэш
for obj in col.find():
    obj_id = obj.pop("_id")
    KEYS.append(str(obj_id))
    setflat_skeys(r, obj, obj_id)


# добавление нового объявления
# при создании сразу пишем его и в бд и в кэш
@app.route('/new', methods=['POST', 'GET'])
def new():
    form = BulForm()
    if form.validate_on_submit():
        new_bul = {
            'author': form.author.data,
            'title': form.title.data,
            'content': form.content.data,
            'tags': make_tags(form.tags.data),
            'creation_time': datetime.now().strftime("%m-%d-%Y, %H:%M:%S")
        }
        col.insert_one(new_bul)
        new_id = new_bul.pop(str("_id"))
        KEYS.append(new_id)
        setflat_skeys(r, new_bul, new_id)
        return redirect('/')
    return render_template('bul_form.html', title='New bulletin', form=form)


# список обьявлений на главной странице. Выбираем из кэша
@app.route('/')
def index():
    buls = []
    for bul in KEYS:
        temp = fish_out_of_cache_simple(r, bul)
        temp['_id'] = bul
        buls.append(temp)
    return render_template('bul_list.html', title='Bulletin list', buls=buls)


# самая основная функция. Позволяет просматривать комменты, тэги
# добавлять их
@app.route('/<rec_number>', methods=['POST', 'GET'])
def detail_view(rec_number):
    # создадим формы
    commentform = CommentForm()
    tagform = TagForm()
    # сохраним начала ключей данного оюъявления в редис
    tag_key = f'{rec_number}:tags'
    comment_key = f'{rec_number}:comments:'
    # выгребаем из кэша простые словари, без вложенностей
    bul = fish_out_of_cache_simple(r, rec_number)
    # если есть тэги, запрашиваем и их, но т.к. они хранятся в виде сета, то для них используется другая команда
    if r.scard(tag_key) > 0:
        bul['tags'] = [x.decode("utf-8") for x in r.smembers(tag_key)]

    # Выбираем из кэша комменты. Перебираем все по очереди, используя начало ключа и счетчик
    # когда оба запроса на предполагаемый контент вернут ничего, останавливаемся
    bul['comments'] = []
    comment_count = 0
    while True:
        author = r.get(f'{comment_key}{comment_count}:author')
        content = r.get(f'{comment_key}{comment_count}:content')
        if not (author and content):
            break
        comment_count += 1
        bul['comments'].append({'author': author.decode("utf-8"), 'content': content.decode("utf-8")})

    # если с формы пришли тэги, превращаем их в массив и закидываем в редис
    # если после этого окажется, что сэт увеличился, переписываем в сэт в бд
    if tagform.validate_on_submit():
        new_tags = make_tags(tagform.tags.data)
        r.sadd(tag_key, *new_tags)
        if r.scard(tag_key) > len(bul['tags']):
            col.update_one({"_id": ObjectId(rec_number)}, {"$set": {"tags": [x.decode("utf-8") for x in r.smembers(tag_key)]}})
        return redirect(url_for('detail_view', rec_number=rec_number))

    # берем новый коммент с формы и записываем и в бд и в кэш
    if commentform.validate_on_submit():
        new_comment = {
            "author": commentform.author.data,
            "content": commentform.content.data,
        }
        col.update_one({"_id": ObjectId(rec_number)}, {"$push": {"comments": new_comment}})
        r.set(f'{comment_key}{comment_count}:author', new_comment['author'])
        r.set(f'{comment_key}{comment_count}:content', new_comment['content'])
        return redirect(url_for('detail_view', rec_number=rec_number))
    return render_template('bul_detail.html', title='Bulletin', bul=bul, cmform=commentform, tgform=tagform)
