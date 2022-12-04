from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo
from flask_babel import _, lazy_gettext as _l
from app.models import User


class LoginForm(FlaskForm):
    username = StringField(_l('Nome de usuário'), validators=[DataRequired()])
    password = PasswordField(_l('Senha'), validators=[DataRequired()])
    remember_me = BooleanField(_l('Lembre-me'))
    submit = SubmitField(_l('Entrar'))


class RegistrationForm(FlaskForm):
    username = StringField(_l('Nome de usuário'), validators=[DataRequired()])
    email = StringField(_l('E-mail'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Senha'), validators=[DataRequired()])
    password2 = PasswordField(
        _l('Repita a senha'), validators=[DataRequired(),
                                           EqualTo('password')])
    submit = SubmitField(_l('Cadastrar'))

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError(_('Por favor, escolha um nome de usuário diferente.'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError(_('Por favor, escolha um endereço de e-mail diferente.'))


class ResetPasswordRequestForm(FlaskForm):
    email = StringField(_l('E-mail'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Solicitar mudança de senha'))


class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Senha'), validators=[DataRequired()])
    password2 = PasswordField(
        _l('Repita a senha'), validators=[DataRequired(),
                                           EqualTo('password')])
    submit = SubmitField(_l('Solicitar mudança de senha'))
