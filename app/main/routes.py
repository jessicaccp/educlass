from datetime import datetime
import sys
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, make_response
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from langdetect import detect, LangDetectException
from app import db
from app.main.forms import EditProfileForm, EmptyForm, PostForm, SearchForm, \
    MessageForm
from app.models import *
from app.translate import translate
from app.main import bp
import app.main.events as evt
from functools import wraps
from random import randint


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if "Admin" in current_user.roles or "Mainteiner" in current_user.roles:
            return f(*args, **kwargs)
        else:
            flash("You need to be an admin to view this page.")
            return redirect(url_for('index'))

    return wrap


@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        try:
            language = detect(form.post.data)
        except LangDetectException:
            language = ''
        post = Post(body=form.post.data, author=current_user,
                    language=language)
        db.session.add(post)
        db.session.commit()
        flash(_('Postagem feita com sucesso!'))
        return redirect(url_for('main.index'))
    page = request.args.get('page', 1, type=int)
    posts = current_user.followed_posts().paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False)
    next_url = url_for('main.index', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.index', page=posts.prev_num) \
        if posts.has_prev else None
    events = Event.query.all()
    events = len(events)
    return render_template('index.html', title=_('Início'), form=form,
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url, events=events)


@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False)
    next_url = url_for('main.explore', page=posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.explore', page=posts.prev_num) \
        if posts.has_prev else None
    return render_template('index.html', title=_('Explorar'),
                           posts=posts.items, next_url=next_url,
                           prev_url=prev_url)


@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
        page=page, per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False)
    next_url = url_for('main.user', username=user.username,
                       page=posts.next_num) if posts.has_next else None
    prev_url = url_for('main.user', username=user.username,
                       page=posts.prev_num) if posts.has_prev else None
    form = EmptyForm()
    return render_template('user.html', title=_('Perfil'), user=user, posts=posts.items,
                           next_url=next_url, prev_url=prev_url, form=form)


@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = User.query.filter_by(username=username).first_or_404()
    form = EmptyForm()
    return render_template('user_popup.html', title=_('Perfil'), user=user, form=form)


@bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Suas alterações foram salvas.'))
        return redirect(url_for('main.edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title=_('Editar Perfil'),
                           form=form)


@bp.route('/follow/<username>', methods=['POST'])
@login_required
def follow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(_('Usuário %(username)s não encontrado.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('Você não pode seguir a si mesmo!'))
            return redirect(url_for('main.user', username=username))
        current_user.follow(user)
        db.session.commit()
        flash(_('Você está seguindo %(username)s!', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow(username):
    form = EmptyForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=username).first()
        if user is None:
            flash(_('Usuário %(username)s não encontrado.', username=username))
            return redirect(url_for('main.index'))
        if user == current_user:
            flash(_('Você não pode deixar de seguir a si mesmo!'))
            return redirect(url_for('main.user', username=username))
        current_user.unfollow(user)
        db.session.commit()
        flash(_('Você não está seguindo %(username)s.', username=username))
        return redirect(url_for('main.user', username=username))
    else:
        return redirect(url_for('main.index'))


@bp.route('/translate', methods=['POST'])
@login_required
def translate_text():
    return jsonify({'text': translate(request.form['text'],
                                      request.form['source_language'],
                                      request.form['dest_language'])})


@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return redirect(url_for('main.explore'))
    page = request.args.get('page', 1, type=int)
    posts, total = Post.search(g.search_form.q.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', q=g.search_form.q.data, page=page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', q=g.search_form.q.data, page=page - 1) \
        if page > 1 else None
    return render_template('search.html', title=_('Pesquisa'), posts=posts,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/send_message/<recipient>', methods=['GET', 'POST'])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username=recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(author=current_user, recipient=user,
                      body=form.message.data)
        db.session.add(msg)
        user.add_notification('unread_message_count', user.new_messages())
        db.session.commit()
        flash(_('Sua mensagem foi enviada.'))
        return redirect(url_for('main.user', username=recipient))
    return render_template('send_message.html', title=_('Enviar Mensagem'),
                           form=form, recipient=recipient)


@bp.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type=int)
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
            page=page, per_page=current_app.config['POSTS_PER_PAGE'],
            error_out=False)
    next_url = url_for('main.messages', page=messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page=messages.prev_num) \
        if messages.has_prev else None
    return render_template('messages.html', title=_('Mensagens'), messages=messages.items,
                           next_url=next_url, prev_url=prev_url)


@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_task_in_progress('export_posts'):
        flash(_('Uma exportação já está em progresso'))
    else:
        current_user.launch_task('export_posts', _('Exportando dados...'))
        db.session.commit()
    return redirect(url_for('main.user', username=current_user.username))


@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type=float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(Notification.timestamp.asc())
    return jsonify([{
        'name': n.name,
        'data': n.get_data(),
        'timestamp': n.timestamp
    } for n in notifications])


@bp.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html', title=_('Calendário'))


@bp.route('/grades')
@login_required
def grades():
    return render_template('grades.html', title=_('Notas'))


@bp.route('/attendance')
@login_required
def attendance():
    return render_template('attendance.html', title=_('Presenças'))


@bp.route('/classroom')
@login_required
def classroom():
    teachers = Teacher.query.all()
    subjects = ['Matemática']
    return render_template('classroom.html', title=_('Turma'), teachers=teachers, subjects=subjects)


@bp.route('/support')
def support():
    return render_template('support.html', title=_('Suporte'))


@bp.route('/terms_and_privacy')
def terms_and_privacy():
    return render_template('terms_and_privacy.html', title=_('Termos e Privacidade'))


@bp.route('/calendario', methods=["GET", "POST"])
@login_required
def calendario():
    return render_template('calendar.html')


@bp.route('/calendario/api/get', methods=["POST"])
@login_required
def get_calendar():
    data = dict(request.form)
    events = evt.get(int(data["month"]), int(data["year"]))
    return "{}" if events is None else events


@bp.route("/calendario/api/save", methods=["POST"])
@login_required
def save():
    data = dict(request.form)
    ok = evt.save(data["s"], data["e"], data["t"], data["c"],
                  data["b"], data["id"] if "id" in data else None)
    msg = "OK" if ok else sys.last_value
    return make_response(msg, 200)


@bp.route("/calendario/api/delete", methods=["POST"])
@login_required
def delete():
    data = dict(request.form)
    ok = evt.delete(data["id"])
    msg = "OK" if ok else sys.last_value
    return make_response(msg, 200)


@bp.route('/init')
def init_db():
    db.session.close()
    db.drop_all()
    db.create_all()

    admin_role = Role(name='Admin')
    maintener_role = Role(name='Mainteiner')
    member_role = Role(name='Member')

    admin_user = User(**{
        'username': 'admin',
        'email': 'admin@gmail.com'
    })

    admin = Person(**{
        'first_name': 'Admin',
        'last_name': 'Istrador',
        'cpf': '000.000.000-00',
    })
    admin_user.set_password('12345')
    legal_user = User(**{
        'username': 'theo',
        'email': 'the@gmail.com'
    })
    legal = LegalGuardian(**{
        'first_name': 'Theobaldo',
        'last_name': 'Primeiro',
        'cpf': '111.111.111-11',
    })
    legal_user.set_password('12345')

    student = Student(**{
        'first_name': 'Nero',
        'last_name': 'Segundo',
        'cpf': '222.222.222-22',
    })
    student_user = User(**{
        'username': 'nero',
        'email': 'nero@gmail.com'
    })
    student_user.set_password('12345')

    student1 = Student(**{
        'first_name': 'Jupiter',
        'last_name': 'Terceiro',
        'cpf': '333.333.333-33',
    })
    student_user1 = User(**{
        'username': 'jupiter',
        'email': 'jupiter@gmail.com'
    })
    student_user1.set_password('12345')

    quimica = Subject(**{
        'name': 'Química'
    })

    matematica = Subject(**{
        'name': 'Matemática'
    })

    literatura = Subject(**{
        'name': 'Literatura'
    })

    fisica = Subject(**{
        'name': 'Física'
    })

    teacher = Teacher(**{
        'first_name': 'Edward ',
        'last_name': 'Crowley',
        'cpf': '939.393.939-39',
        'salary': '12.000,00',
        'subject': quimica,
        'person_type': 'employee'
    })
    teacher_user = User(**{
        'username': 'crowley',
        'email': 'crowley@gmail.com'
    })
    teacher_user.set_password('12345')

    teacher1 = Teacher(**{
        'first_name': 'Dion',
        'last_name': 'Fortune',
        'cpf': '444.444.444-44',
        'salary': '12.000,00',
        'subject': matematica,
        'person_type': 'employee'
    })
    teacher_user1 = User(**{
        'username': 'dion',
        'email': 'dion@gmail.com'
    })
    teacher_user1.set_password('12345')

    teacher2 = Teacher(**{
        'first_name': 'Alphonse',
        'last_name': 'Constant',
        'cpf': '555.555.555-555',
        'salary': '12.000,00',
        'subject': literatura,
        'person_type': 'employee'
    })
    teacher_user2 = User(**{
        'username': 'alphonse',
        'email': 'alphonse@gmail.com'
    })
    teacher_user2.set_password('12345')

    teacher3 = Teacher(**{
        'first_name': 'Samuel',
        'last_name': 'Mathers',
        'cpf': '666.666.666-66',
        'salary': '12.000,00',
        'subject': fisica,
        'person_type': 'employee'
    })
    teacher_user3 = User(**{
        'username': 'samuel',
        'email': 'samuel@gmail.com'
    })
    teacher_user3.set_password('12345')

    student.legal_guardian = legal
    student1.legal_guardian = legal

    stu_sub = StudentSubject(fault=randint(
        0, 10), attendence=randint(5, 20), score=randint(1, 100), subject=matematica, student=student)
    stu_sub2 = StudentSubject(fault=randint(
        0, 10), attendence=randint(5, 20), score=randint(1, 100), subject=literatura, student=student)

    stu_sub3 = StudentSubject(fault=randint(
        0, 10), attendence=randint(5, 20), score=randint(1, 100), subject=fisica, student=student1)
    stu_sub4 = StudentSubject(fault=randint(
        0, 10), attendence=randint(5, 20), score=randint(1, 100), subject=quimica, student=student1)

    admin_user.person = admin
    admin_user.roles = [admin_role, maintener_role, member_role]

    legal_user.person = legal
    legal_user.roles = [member_role]

    student_user.person = student1
    student_user.roles = [member_role]
    student_user1.person = student1
    student_user1.roles = [member_role]

    teacher_user.roles = [maintener_role, member_role]
    teacher_user.person = teacher

    classroom1 = Classroom(id=1)
    classroom1.students.append(student)
    classroom1.teachers.append(teacher)
    classroom1.teachers.append(teacher1)

    classroom2 = Classroom(id=2)
    classroom2.students.append(student1)
    classroom2.teachers.append(teacher2)
    classroom2.teachers.append(teacher3)

    events1 = [
        Event(
            start=datetime.fromisoformat('2022-12-19 03:00:00'),
            end=datetime.fromisoformat('2022-12-30 03:00:00'),
            text='Férias',
            color='#000000',
            bg='#1aa7ec'
        ),
        Event(
            start=datetime.fromisoformat('2022-12-05 03:00:00'),
            end=datetime.fromisoformat('2022-12-09 03:00:00'),
            text='Semana de provas',
            color='#000000',
            bg='#ffdbdb'
        )
    ]

    events2 = [
        Event(
            start=datetime.fromisoformat('2022-12-19 03:00:00'),
            end=datetime.fromisoformat('2022-12-30 03:00:00'),
            text='Férias',
            color='#000000',
            bg='#1aa7ec'
        ),
        Event(
            start=datetime.fromisoformat('2022-12-12 03:00:00'),
            end=datetime.fromisoformat('2022-12-16 03:00:00'),
            text='Semana de provas',
            color='#000000',
            bg='#ffdbdb'
        )
    ]

    calendar1 = Calendar()
    calendar1.events = events1
    classroom1.calendar = calendar1

    calendar2 = Calendar()
    calendar2.events = events2
    classroom2.calendar = calendar2

    db.session.add(admin_user)
    db.session.add(legal_user)
    db.session.add(student_user)
    db.session.add(student_user1)
    db.session.add(teacher_user)
    db.session.add(teacher_user1)
    db.session.add(teacher_user2)
    db.session.add(teacher_user3)
    db.session.add(classroom1)
    db.session.add(classroom2)
    db.session.commit()

    return 'Deu bom'
