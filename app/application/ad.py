# l = ldap.initialize('ldap://x.x.x.x')
# l.simple_bind_s('xxx@su.local', 'pasword')
#  l.search_s("CN=firstname lastname,OU=Beheerders,OU=Accounts,DC=SU,DC=local", ldap.SCOPE_SUBTREE, attrlist=["cn"])
# l.modify_s("CN=firstname lastname,OU=Beheerders,OU=Accounts,DC=SU,DC=local", [(ldap.MOD_REPLACE, "info", [b"nieuwe info"])])
# wwwhomepage: leerlingnummer
# pager: rfid
# postofficebox: computer
# l.search_s("CN=1A,OU=Klassen,OU=Groepen,DC=SU,DC=local", ldap.SCOPE_SUBTREE, attrlist=["member"])
# l.search_s(b"CN=F\xc3\xa9 Dieltjens,OU=2020-2021,OU=Leerlingen,OU=Accounts,DC=SU,DC=local".decode("utf-8"), ldap.SCOPE_SUBTREE)
# https://social.technet.microsoft.com/wiki/contents/articles/5392.active-directory-ldap-syntax-filters.aspx
# filter : "(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))" enabled/active user
# filter : "(&(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=2))" disabled/inactive user

# l.rename_s('CN=Evelien Merckx,OU=terug,OU=2020-2021,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', 'CN=Evelien Merckx', "OU=2021-2022,OU=Leerlingen,OU=Accounts,DC=SU,DC=local")
# move evelien from 2020-2021/terug to 2021-2022

#all ou's under leerlingen:  l.search_s("OU=Leerlingen,OU=Accounts,DC=SU,DC=local", ldap.SCOPE_SUBTREE, "(objectCategory=Organizationalunit)")

# use ldap3 (pip install ldap3)
# from ldap3 import Server, Connection, SAFE_SYNC

# s = ldap3.Server('ldaps://x.x.x.x', use_ssl=True)
# ldap_s = ldap3.Connection(s, 'su.local\\<user>', '<pasword>', auto_bind=True, authentication=ldap3.NTLM)
# ldap3.extend.microsoft.modifyPassword.ad_modify_password(ldap_s, 'CN=manuel test,OU=manuel-test,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', 'Azerty12', None)
# set password empty
# ldap3.extend.microsoft.modifyPassword.ad_modify_password(ldap, 'CN=M-Akhunbaev Deniz,OU=2026-2027,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', '', None)
# user must change password at next logon
# ldap.modify('CN=M-Akhunbaev Deniz,OU=2026-2027,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', changes={"pwdLastSet": (ldap3.MODIFY_REPLACE, [0])})
# status, result, response, _ = conn.search('o=test', '(objectclass=*)')  # usually yo
# conn.add('OU=manuel-test,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', 'organizationalunit') # add OU manuel-test
# ret = conn.search('OU=Leerlingen,OU=Accounts,DC=SU,DC=local', '(objectclass=*)')  returns true or false
# conn.response : return values returned
# conn.search('OU=Leerlingen,OU=Accounts,DC=SU,DC=local', '(objectclass=organizationalunit)', SUBTREE, attributes=ALL_ATTRIBUTES)
# move user to other OU
# ldap_s.modify("CN=manuel test,OU=manuel-test,OU=Leerlingen,OU=Accounts,DC=SU,DC=local", {'description': [(ldap3.MODIFY_REPLACE, 'dit is een test')]})
# conn.modify_dn('CN=Rik Fabri,OU=2018-2019,OU=Leerlingen,OU=Accounts,DC=SU,DC=local', 'CN=Rik Fabri', new_superior='OU=manuel-test,OU=Leerlingen,OU=Accounts,DC=SU,DC=local')
#  attributes = {'samaccountname': 's66666', 'wwwhomepage': '66666', 'name': 'manuel test', 'useraccountcontrol': 544, 'cn': 'manuel test', 'sn': 'test', 'l': 'manuel-6IT', 'description': 'manuel-test manuel-6IT', 'postalcode': '26-27', 'physicalDeliveryOfficeName': 'manuel-6IT', 'givenname': 'manuel', 'displayname': 'manuel test'}
# ldap_s.add(f'CN=manuel-test,{klas_location_toplevel}', 'group', {'cn': 'manuel-test', 'member': 'CN=Michiel Smans,OU=2021-2022,OU=Leerlingen,OU=Accounts,DC=SU,DC=local'})

from app import log
from app.data import student as mstudent
from app.data import settings as msettings
import ldap3, json, sys


class Context:
    def __init__(self):
        self.check_properties_changed = ['naam', 'voornaam', 'klascode', 'schooljaar', 'rifd', 'computer']
        self.student_location_toplevel = 'OU=Leerlingen,OU=Accounts,DC=SU,DC=local'
        self.klas_location_toplevel = 'OU=Klassen,OU=Groepen,DC=SU,DC=local'
        self.leerlingen_group = 'CN=Leerlingen,OU=Groepen,DC=SU,DC=local'
        self.email_domain = '@lln.campussintursula.be'
        self.student_location_current_year = ''
        self.ad_active_students_leerlingnummer = {}  # cache active students, use leerlingnummer as key
        self.ad_active_students_cn = {}  # cache active students, use cn as key
        self.leerlingnummer_to_klas = {} # find a klas a student belongs to, use leerlingnummer as key
        self.ad_klassen = []
        self.add_student_to_klas = {}  # dict of klassen with list-of-students-to-add-to-the-klas
        self.delete_student_from_klas = {}  # dict of klassen with list-of-students-to-delete-from-the-klas
        self.new_students_to_add = []  # these students do not exist yet in AD, must be added
        self.move_students_to_current_year_ou = []
        self.students_must_update_password = []
        self.changed_schoolyear = False
        self.prev_year = ''
        self.current_year = ''
        self.ldap = None


normalMap = {'??': 'A', '??': 'A', '??': 'A', '??': 'A', '??': 'A','??': 'a', '??': 'a', '??': 'a', '??': 'a', '??': 'a', '??': 'A',
             '??': 'E', '??': 'E', '??': 'E', '??': 'E', '??': 'e', '??': 'e', '??': 'e', '??': 'e',
             '??': 'I', '??': 'I', '??': 'I', '??': 'I','??': 'i', '??': 'i', '??': 'i', '??': 'i',
             '??': 'O', '??': 'O', '??': 'O', '??': 'O', '??': 'O', '??': 'o', '??': 'o', '??': 'o', '??': 'o', '??': 'o', '??': 'O', '??': 'O',
             '??': 'U', '??': 'U', '??': 'U', '??': 'U','??': 'u', '??': 'u', '??': 'u', '??': 'u',
             '??': 'N', '??': 'n',
             '??': 'C', '??': 'c',
             '??': 'S',  '??': '3', '??': '2', '??': '1'}
normalize = str.maketrans(normalMap)


# move/add/delete student from/to a klas
def update_klassen_prepare(ctx, student):
    try:
        if student.new or 'klascode' in student.changed:
            if student.klascode in ctx.add_student_to_klas:
                ctx.add_student_to_klas[student.klascode].append(ctx.ad_active_students_leerlingnummer[student.leerlingnummer]['dn'])
            else:
                ctx.add_student_to_klas[student.klascode] = [ctx.ad_active_students_leerlingnummer[student.leerlingnummer]['dn']]
        if student.delete or 'klascode' in student.changed:
            if student.leerlingnummer in ctx.leerlingnummer_to_klas:
                current_klas = ctx.leerlingnummer_to_klas[student.leerlingnummer]
                if current_klas in ctx.delete_student_from_klas:
                    ctx.delete_student_from_klas[current_klas].append(ctx.ad_active_students_leerlingnummer[student.leerlingnummer]['dn'])
                else:
                    ctx.delete_student_from_klas[current_klas] = [ctx.ad_active_students_leerlingnummer[student.leerlingnummer]['dn']]
            else:
                log.error(f'AD, update klassen prepare, student {student.leerlingnummer} not found in AD')
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')



def update_klassen_apply_to_ad(ctx):
    try:
        for klas, members in ctx.delete_student_from_klas.items():
            klas_dn = f'CN={klas},{ctx.klas_location_toplevel}'
            res = ctx.ldap.modify(klas_dn, {'member': [(ldap3.MODIFY_DELETE, members)]})
            if res:
                log.info(f'AD: removed from klas {klas_dn} members {members}')
            else:
                log.error(f'AD: could not remove from klas {klas_dn} members {members}')
        # add students to klassen
        for klas, members in ctx.add_student_to_klas.items():
            klas_dn = f'CN={klas},{ctx.klas_location_toplevel}'
            if klas not in ctx.ad_klassen:
                ctx.ad_klassen.append(klas)
                res = ctx.ldap.add(klas_dn, 'group', {'cn': f'{klas}', 'member': members})
                if res:
                    log.info(f'AD: added new klas {klas}')
                else:
                    log.error(f'AD: could not add klas {klas}')
            else:
                res = ctx.ldap.modify(klas_dn, {'member': [(ldap3.MODIFY_ADD, members)]})
                if res:
                    log.info(f'AD: added to klas {klas_dn} members {members}')
                else:
                    log.error(f'AD: could not add to klas {klas_dn} members {members}')
        # remove empty klassen
        res = ctx.ldap.search(ctx.klas_location_toplevel, '(&(objectclass=group)(!(member=*)))', attributes=['cn'])
        if res:
            ad_klassen = ctx.ldap.response
            for klas in ad_klassen:
                res = ctx.ldap.delete(klas['dn'])
                if res:
                    log.info(f'AD, removed empty klas {klas["dn"]}')
                else:
                    log.error(f'AD, could not remove empty klass {klas["dn"]}')
            log.info(f'AD, removed {len(ad_klassen)} empty klassen')
        else:
            log.error('AD, could not remove empty klassen')
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def init():
    try:
        ctx = Context()
        ctx.changed_schoolyear, ctx.prev_year, ctx.current_year = msettings.get_changed_schoolyear()
        if ctx.changed_schoolyear:  # keep a local copy of changed-schoolyear
            msettings.set_configuration_setting('ad-schoolyear-changed', True)
        ctx.changed_schoolyear = msettings.get_configuration_setting('ad-schoolyear-changed')
        ad_host = msettings.get_configuration_setting('ad-url')
        ad_login = msettings.get_configuration_setting('ad-login')
        ad_password = msettings.get_configuration_setting('ad-password')
        ldap_server = ldap3.Server(ad_host, use_ssl=True)
        ctx.ldap = ldap3.Connection(ldap_server, ad_login, ad_password, auto_bind=True, authentication=ldap3.NTLM)
        # Create student caches
        res = ctx.ldap.search(ctx.student_location_toplevel, f'(&(objectclass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))', ldap3.SUBTREE, attributes=['cn', 'wwwhomepage', 'userAccountControl'])
        if res:
            ctx.ad_active_students_leerlingnummer = {s['attributes']['wwwhomepage']: s for s in ctx.ldap.response if s['attributes']['wwwhomepage'] != []}
            ctx.ad_active_students_cn = {s['dn']: s for s in ctx.ldap.response if s['attributes']['wwwhomepage'] != []}
            log.info(f'AD: create active-students-caches, {len(ctx.ad_active_students_leerlingnummer)} entries')
        else:
            log.error('AD: could not create active-students-caches')

        # Create klas caches
        res = ctx.ldap.search(ctx.klas_location_toplevel, '(objectclass=group)', ldap3.SUBTREE, attributes=['member', 'cn'])
        if res:
            for klas in ctx.ldap.response:
                ctx.ad_klassen.append(klas['attributes']['cn'])
                ctx.leerlingnummer_to_klas.update({ctx.ad_active_students_cn[m]['attributes']['wwwhomepage']: klas['attributes']['cn'] for m in klas['attributes']['member'] if m in ctx.ad_active_students_cn})
            log.info(f'AD: create student-to-leerlingnummer-cache, with {len(ctx.leerlingnummer_to_klas)} entries')
        else:
            log.error('AD: could not create student-to-leerlingnummer-cache')
        return ctx
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def deinit(ctx):
    try:
        ctx.ldap.unbind()
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def create_current_year_ou(ctx):
    try:
        # check if OU current year exists.  If not, create
        find_current_year_ou = ctx.ldap.search(ctx.student_location_toplevel, f'(&(objectclass=organizationalunit)(name={ctx.current_year}))', ldap3.SUBTREE)
        if not find_current_year_ou:
            res = ctx.ldap.add(f'OU={ctx.current_year},{ctx.student_location_toplevel}', 'organizationalunit')
            if res:
                log.info(f'AD: added new OU: {ctx.current_year}')
            else:
                log.error(f'AD error: could not add OU {ctx.current_year}, aborting...')
                return False
        ctx.student_location_current_year = f'OU={ctx.current_year},{ctx.student_location_toplevel}'
        return True
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def new_students(ctx):
    try:
        # check if new student already exists in AD (student left school and came back)
        # if so, activate and put in current OU
        new_students = mstudent.get_students({"new": True})
        log.info('AD: new students: if student is already in AD: activate and put in current year OU')
        for student in new_students:
            res = ctx.ldap.search(ctx.student_location_toplevel, f'(&(objectclass=user)(wwwhomepage={student.leerlingnummer}))', ldap3.SUBTREE, attributes=['cn', 'userAccountControl'])
            if res:  # student already in AD, but inactive and probably in wrong OU and wrong klas
                ad_student = ctx.ldap.response[0]
                dn = ad_student['dn']  # old OU
                account_control = ad_student['attributes']['userAccountControl']  # to activate
                ctx.move_students_to_current_year_ou.append(ad_student)
                ctx.students_must_update_password.append(ad_student)
                account_control &= ~2  # clear bit 2 to activate
                changes = {
                    'userAccountControl': [(ldap3.MODIFY_REPLACE, [account_control])],
                    'description': [ldap3.MODIFY_REPLACE, (f'{student.schooljaar} {student.klascode}')],
                    'postalcode': [ldap3.MODIFY_REPLACE, (student.schooljaar,)],
                    'l': [ldap3.MODIFY_REPLACE, (student.klascode)],
                    'physicalDeliveryOfficeName': [ldap3.MODIFY_REPLACE, (student.klascode)],
                    "pwdLastSet": [(ldap3.MODIFY_REPLACE, [0])]   # student must update password at first login
                }
                if student.rfid and student.rfid != '':
                    changes.update({'pager': [ldap3.MODIFY_REPLACE, (student.rfid)]})
                res = ctx.ldap.modify(dn, changes)
                if not res:
                    log.error(f'AD error, could not activate {dn}, with changes {changes}')
                res = ldap3.extend.microsoft.modifyPassword.ad_modify_password(ctx.ldap, dn, '', None)  # reset the password to empty
                if not res:
                    log.error(f'AD error, could clear password of {dn}')
                # add student to cache
                ctx.ad_active_students_leerlingnummer[student.leerlingnummer] = ad_student
                update_klassen_prepare(ctx, student)
            else:
                ctx.new_students_to_add.append(student)
        log.info('AD: add (create) new students to current year OU')

        # add new students to current OU
        # new students are created with empty password and are required to set a password at first login
        object_class = ['top', 'person', 'organizationalPerson', 'user']
        for student in ctx.new_students_to_add:
            attributes = {'samaccountname': f's{student.leerlingnummer}', 'wwwhomepage': f'{student.leerlingnummer}',
                          'userprincipalname': f's{student.leerlingnummer}{ctx.email_domain}',
                          'mail': f'{student.voornaam.translate(normalize)}.{student.naam.translate(normalize)}{ctx.email_domain}',
                          'name': f'{student.naam} {student.voornaam}',
                          'useraccountcontrol': 0X220,     #password not required, normal account, account active
                          'cn': f'{student.naam} {student.voornaam}',
                          'sn': student.naam,
                          'l': student.klascode,
                          'description': f'{student.schooljaar} {student.klascode}', 'postalcode': student.schooljaar,
                          'physicaldeliveryofficename': student.klascode, 'givenname': student.voornaam,
                          'displayname': f'{student.naam} {student.voornaam}'}
            if student.rfid and student.rfid != '':
                attributes['pager'] = student.rfid
            cn = f'{student.naam} {student.voornaam}'
            dn = f'CN={cn},{ctx.student_location_current_year}'
            res = ctx.ldap.add(dn, object_class, attributes)
            if not res:
                log.error(f'AD: could not add new student with attributes: {attributes}')
            ctx.ad_active_students_leerlingnummer[student.leerlingnummer] = {'dn': dn, 'attributes': {'cn': cn}}
            update_klassen_prepare(ctx, student)
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def changed_students(ctx):
    try:
        # check if there are students with valid, changed attributes.  If so, update the attributes
        # if required, move the students to the current OU
        log.info('AD: check for changed students')
        changed_students = mstudent.get_students({"-changed": "", "new": False})
        if changed_students:
            for student in changed_students:
                changed = json.loads(student.changed)
                if list(set(ctx.check_properties_changed).intersection(changed)):
                    if student.leerlingnummer in ctx.ad_active_students_leerlingnummer:
                        changes = {}
                        if 'naam' in changed or 'voornaam' in changed:
                            changes.update({'name': [ldap3.MODIFY_REPLACE, (f'{student.naam} {student.voornaam}')],
                                            'cn': [ldap3.MODIFY_REPLACE, (f'{student.naam} {student.voornaam}')],
                                            'sn': [ldap3.MODIFY_REPLACE, (student.naam)],
                                            'givenname': [ldap3.MODIFY_REPLACE, (student.voornaam)],
                                            'displayname': [ldap3.MODIFY_REPLACE, (f'{student.naam} {student.voornaam}')]})
                        if 'rfid' in changed:
                            changes.update({'pager': [ldap3.MODIFY_REPLACE, (student.rfid)]})
                        if 'schooljaar' in changed or 'klascode' in changed:
                            changes.update(
                                {'description': [ldap3.MODIFY_REPLACE, (f'{student.schooljaar} {student.klascode}')],
                                 'postalcode': [ldap3.MODIFY_REPLACE, (student.schooljaar,)],
                                 'l': [ldap3.MODIFY_REPLACE, (student.klascode)],
                                 'physicalDeliveryOfficeName': [ldap3.MODIFY_REPLACE, (student.klascode)]})
                        res = ctx.ldap.modify(ctx.ad_active_students_leerlingnummer[student.leerlingnummer]['dn'], changes)
                        if not res:
                            log.error(f'AD error: could not update changes of {student.leerlingnummer}: {changes}')
                        if 'schooljaar' in changed:  # move to new OU
                            ctx.move_students_to_current_year_ou.append(ctx.ad_active_students_leerlingnummer[student.leerlingnummer])
                        if 'klascode' in changed:
                            update_klassen_prepare(ctx, student)
                    else:
                        log.error(f'AD error: student {student.leerlingnummer} is not active in AD')
        log.info(f'AD, updated {len(changed_students)} students')
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def deleted_students(ctx):
    try:
        log.info('AD: check for deleted students')
        deleted_students = mstudent.get_students({"delete": True})
        if deleted_students:
            for student in deleted_students:
                ad_student = ctx.ad_active_students_leerlingnummer[student.leerlingnummer]
                dn = ad_student['dn']
                account_control = ad_student['attributes']['userAccountControl']  # to activate
                account_control |= 2  # set bit 2 to deactivate
                changes = {'userAccountControl': [(ldap3.MODIFY_REPLACE, [account_control])]}
                res = ctx.ldap.modify(dn, changes)
                if not res:
                    log.error(f'AD error, could not deactivate {dn}')
                update_klassen_prepare(ctx, student)
        log.info(f'AD, deleted {len(deleted_students)} students')

    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def move_students_to_current_year_ou(ctx):
    try:
        log.info('AD, move students to the current schoolyear OU')
        for student in ctx.move_students_to_current_year_ou:
            res = ctx.ldap.modify_dn(student['dn'], f"CN={student['attributes']['cn']}", new_superior=ctx.student_location_current_year)
            if not res:
                log.error(f'AD error, could not move {student.leerlingnummer} from {ctx.ad_active_students_leerlingnummer[student.leerlingnummer]["dn"]} to {ctx.student_location_current_year}')
        log.info(f'AD, moved {len(ctx.move_students_to_current_year_ou)} to the current schoolyear OU')
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def students_must_update_password(ctx):
    try:
        log.info('AD, students must update password')
        for student in ctx.students_must_update_password:
            dn = f'CN={student["attributes"]["cn"]},{ctx.student_location_current_year}'
            changes = {"pwdLastSet": [(ldap3.MODIFY_REPLACE, [0])]}  # student must update password at first login
            res = ctx.ldap.modify(dn, changes)
            if not res:
                log.error(f'AD error, update setting of {dn}, with changes {changes}')
        log.info(f'AD, {len(ctx.move_students_to_current_year_ou)} students must update their password')
    except Exception as e:
        log.error(f'{sys._getframe().f_code.co_name}: {e}')


def update_ad():
    try:
        log.info(('Start update to AD'))
        ctx = init()
        if not create_current_year_ou(ctx):
            deinit(ctx)
            return
        new_students(ctx)
        changed_students(ctx)
        deleted_students(ctx)
        update_klassen_apply_to_ad(ctx) # first update the klassen because the dn refers to the previous schoolyear OU
        move_students_to_current_year_ou(ctx) # then move the students to the current schoolyear OU
        # for some reason, it is only possible to change the setting to update the password AFTER the student is moved to the new OU
        students_must_update_password(ctx) # then change a setting so that the student must update the password
        deinit(ctx)
        msettings.set_configuration_setting('ad-schoolyear-changed', False)
        log.info(f'update_ad: processed ')
    except Exception as e:
        log.error(f'update from wisa error: {e}')


def ad_cron_task(opaque):
    if msettings.get_configuration_setting('cron-enable-update-student-ad'):
        update_ad()

