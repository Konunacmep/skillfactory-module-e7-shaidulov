from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired


class TagForm(FlaskForm):
    tags = StringField('Добавить тэги, можно несколько, разделив запятой', validators=[DataRequired()])
    submit = SubmitField('OK')


class CommentForm(FlaskForm):
    author = StringField('Автор', default='anon', validators=[DataRequired()])
    content = StringField('Текст', validators=[DataRequired()])
    submit = SubmitField('OK')


class BulForm(FlaskForm):
    author = StringField('Автор', validators=[DataRequired()])
    title = StringField('Заголовок', validators=[DataRequired()])
    content = StringField('Текст', validators=[DataRequired()])
    tags = StringField('Тэги, можно несколько, разделив запятой')
    submit = SubmitField('OK')
