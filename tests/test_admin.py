import time
from server.db import get_db, transaction
from server.security import BROWSER_COOKIE, digest
from conftest import PASSWORD, administrator, bind, bootstrap, post, spin
from test_event import allocations


def test_amanda_participant_has_no_admin_privilege(app):
    client = app.test_client(); state = bind(client)
    assert state['participant']['name'] == 'Amanda'
    assert client.get('/api/admin/dashboard').status_code == 401
    for path in ['/admin/reveal', '/admin/names', '/admin/reset', f"/admin/participants/{state['participant']['id']}/replay", f"/admin/participants/{state['participant']['id']}/new-draw", f"/admin/participants/{state['participant']['id']}/recovery"]:
        assert post(client, path, state).status_code == 401


def test_admin_requires_own_csrf_and_reveal_is_deliberate(app):
    participant = app.test_client(); state = bind(participant); spin(participant, state)
    admin, session = administrator(app)
    dashboard = admin.get('/api/admin/dashboard').json
    assert 'recipient' not in str(dashboard) and 'assignments' not in dashboard
    assert post(admin, '/admin/reveal', session).status_code == 400
    assert post(admin, '/admin/reveal', state, {'confirmation': 'REVEAL ASSIGNMENTS'}).status_code == 403
    reveal = post(admin, '/admin/reveal', session, {'confirmation': 'REVEAL ASSIGNMENTS'})
    assert len(reveal.json['assignments']) == 1
    assert 'assignments_revealed' in str(admin.get('/api/admin/dashboard').json['audit'])


def test_replay_preserves_every_allocation(app):
    participant = app.test_client(); state = bind(participant); original = spin(participant, state).json
    admin, session = administrator(app); before = allocations(app)
    response = post(admin, f"/admin/participants/{state['participant']['id']}/replay", session, {'event_id': state['event_id']})
    assert response.status_code == 200
    updated = bootstrap(participant)
    assert updated['draw'] == original['draw'] and allocations(app) == before
    assert updated['participant']['replay_version'] == 1


def test_new_draw_preserves_every_other_completed_assignment(app):
    clients = [app.test_client() for _ in range(8)]
    states = [bind(c) for c in clients]
    for c,s in zip(clients,states): assert spin(c,s).status_code == 200
    before = allocations(app); target = states[0]['participant']['id']
    admin, session = administrator(app)
    path = f'/admin/participants/{target}/new-draw'
    assert post(admin, path, session, {'event_id': states[0]['event_id'], 'confirmation': 'oops'}).status_code == 400
    assert allocations(app) == before
    assert post(admin, path, session, {'event_id': states[0]['event_id'], 'confirmation': 'NEW DRAW', 'draw_version': 0}).status_code == 200
    assert allocations(app) == {k:v for k,v in before.items() if k != target}
    assert spin(clients[0], states[0]).status_code == 401  # Stale browser cannot recreate the old draw.
    fresh = bootstrap(clients[0])
    assert fresh['draw'] is None and fresh['participant'] is None
    assert fresh['binding_lost'] is False
    assert [p['id'] for p in fresh['participants'] if not p['claimed']] == [target]
    fresh = bind(clients[0], target)
    assert fresh['segments'] == [{'id': before[target], 'name': next(p['name'] for p in fresh['participants'] if p['id'] == before[target])}]
    assert spin(clients[0], fresh).status_code == 200
    assert allocations(app) == before  # With seven completed draws, the same recipient is forced.
    assert 'new_draw_granted' in str(admin.get('/api/admin/dashboard').json['audit'])


def test_recovery_is_one_use_keeps_result_and_revokes_old_browser(app):
    old = app.test_client(); state = bind(old); original = spin(old,state).json['draw']
    admin, session = administrator(app)
    response = post(admin, f"/admin/participants/{state['participant']['id']}/recovery", session,
                    {'event_id':state['event_id'], 'confirmation':'RESET BROWSER LINK'})
    assert response.status_code == 200
    token = response.json['recovery_url'].split('#recover=')[1]
    assert bootstrap(old)['binding_lost'] is True
    assert spin(old,state).status_code == 409
    assert post(old,'/claim',bootstrap(old),{'event_id':state['event_id'],'participant_id':state['participants'][1]['id']}).status_code == 409
    # Another participant's bound browser cannot be changed through recovery either.
    other = app.test_client(); other_state = bind(other)
    assert post(other,'/recover',other_state,{'token':token}).status_code == 409
    new = app.test_client(); new_state = bootstrap(new)
    result = post(new,'/recover',new_state,{'token':token})
    assert result.status_code == 200 and result.json['draw'] == original
    third = app.test_client()
    assert post(third,'/recover',bootstrap(third),{'token':token}).status_code == 410
    with app.app_context():
        assert get_db().execute('SELECT token_hash FROM recovery_tokens').fetchone()[0] == digest(token)


def test_expired_and_replaced_recovery_links_are_invalid(app):
    client = app.test_client(); state = bind(client); admin, session = administrator(app)
    def issue():
        return post(admin,f"/admin/participants/{state['participant']['id']}/recovery",session,
                    {'event_id':state['event_id'],'confirmation':'RESET BROWSER LINK'}).json['recovery_url'].split('#recover=')[1]
    old_token = issue(); new_token = issue()
    fresh = app.test_client(); fresh_state = bootstrap(fresh)
    assert post(fresh,'/recover',fresh_state,{'token':old_token}).status_code == 410
    with app.app_context(), transaction() as db:
        db.execute('UPDATE recovery_tokens SET expires_at=?', (time.time()-1,))
    assert post(fresh,'/recover',fresh_state,{'token':new_token}).status_code == 410


def test_full_reset_clears_claims_draws_and_invalidates_old_sessions(app):
    client = app.test_client(); state = bind(client); spin(client,state)
    admin, session = administrator(app)
    assert post(admin,'/admin/reset',session,{'event_id':state['event_id'],'confirmation':'RESET'}).status_code == 400
    assert post(admin,'/admin/reset',session,{'event_id':state['event_id'],'confirmation':'RESET ENTIRE EVENT'}).status_code == 200
    assert spin(client,state).status_code == 409
    fresh = bootstrap(client)
    assert fresh['event_id'] != state['event_id'] and fresh['participant'] is None
    assert not any(p['claimed'] for p in fresh['participants']) and fresh['completed_count'] == 0
    assert allocations(app) == {}
    assert admin.get('/api/admin/dashboard').status_code == 200
    assert post(admin,'/admin/reset',session,{'event_id':state['event_id'],'confirmation':'RESET ENTIRE EVENT'}).status_code == 409


def test_admin_names_update_saved_labels_without_changing_assignments(app):
    admin, session = administrator(app)
    dashboard = admin.get('/api/admin/dashboard').json
    names = ['Amanda','Ben','Cara','Dan','Ella','Finn','Gina','Hugo']
    body = {'event_id':dashboard['event_id'],'revision':dashboard['revision'],'names':names}
    assert post(admin,'/admin/names',session,{**body,'names':['Same']*8}).status_code == 400
    assert post(admin,'/admin/names',session,body).status_code == 200
    clients = [app.test_client() for _ in range(2)]
    originals = []
    for client in clients:
        state = bind(client)
        originals.append(spin(client,state).json)
    before = allocations(app)
    updated_names = ['Amanda Smith','Benedict','Carla','Danie','Elsa','Freddie','Gerda','Hennie']
    # Claims and draws may have progressed while Amanda was typing.
    response = post(admin,'/admin/names',session,{**body,'original_names':names,'names':updated_names})
    assert response.status_code == 200, response.json
    assert allocations(app) == before
    ids = [person['id'] for person in originals[0]['participants']]
    display_names = dict(zip(ids,updated_names))
    for client, original in zip(clients, originals):
        current = bootstrap(client)
        assert current['participant']['id'] == original['participant']['id']
        assert current['participant']['name'] == display_names[current['participant']['id']]
        assert current['draw']['recipient']['id'] == original['draw']['recipient']['id']
        assert current['draw']['recipient']['name'] == display_names[current['draw']['recipient']['id']]
        assert current['draw']['drawn_at'] == original['draw']['drawn_at']
        assert [segment['id'] for segment in current['draw']['segments']] == [segment['id'] for segment in original['draw']['segments']]
        assert all(segment['name'] == display_names[segment['id']] for segment in current['draw']['segments'])
    assert post(clients[0],'/admin/names',bootstrap(clients[0]),{'event_id':body['event_id'],'original_names':updated_names,'names':names}).status_code == 401


def test_stale_admin_tab_cannot_overwrite_newer_names(app):
    admin, session = administrator(app)
    dashboard = admin.get('/api/admin/dashboard').json
    original_names = [person['name'] for person in dashboard['participants']]
    names = ['Amanda','Ben','Cara','Dan','Ella','Finn','Gina','Hugo']
    body = {'event_id':dashboard['event_id'],'original_names':original_names,'names':names}
    assert post(admin,'/admin/names',session,body).status_code == 200
    stale = post(admin,'/admin/names',session,{**body,'names':list(reversed(names))})
    assert stale.status_code == 409 and stale.json['code'] == 'names_changed'
    assert [person['name'] for person in bootstrap(app.test_client())['participants']] == names


def test_login_rate_limit_is_persistent_and_logout_revokes_session(app):
    client = app.test_client(); state = client.get('/api/admin/session').json
    for _ in range(5):
        assert post(client,'/admin/login',state,{'password':'incorrect'}).status_code == 401
    assert post(client,'/admin/login',state,{'password':PASSWORD}).status_code == 429
    with app.app_context(), transaction() as db:
        db.execute('UPDATE login_limits SET window_start=?',(time.time()-901,))
    response = post(client,'/admin/login',state,{'password':PASSWORD})
    assert response.status_code == 200
    assert post(client,'/admin/logout',response.json).status_code == 200
    assert client.get('/api/admin/dashboard').status_code == 401


def test_admin_can_correct_wrong_name_using_recovery_for_unclaimed_name(app):
    wrong_browser = app.test_client(); wrong = bind(wrong_browser)
    actual_id = wrong['participants'][1]['id']
    admin, session = administrator(app)
    def recovery_for(person_id):
        response = post(admin,f'/admin/participants/{person_id}/recovery',session,
                        {'event_id':wrong['event_id'],'confirmation':'RESET BROWSER LINK'})
        assert response.status_code == 200
        return response.json['recovery_url'].split('#recover=')[1]
    # Reserve the mistaken selection for its real owner, and revoke the wrong binding.
    correct_owner_link = recovery_for(wrong['participant']['id'])
    actual_link = recovery_for(actual_id)
    changed = post(wrong_browser,'/recover',bootstrap(wrong_browser),{'token':actual_link})
    assert changed.status_code == 200 and changed.json['participant']['id'] == actual_id
    correct_owner = app.test_client()
    restored = post(correct_owner,'/recover',bootstrap(correct_owner),{'token':correct_owner_link})
    assert restored.status_code == 200 and restored.json['participant']['id'] == wrong['participant']['id']


def test_retry_of_old_admin_confirmation_cannot_reset_replacement_draw(app):
    client = app.test_client(); state = bind(client); spin(client,state)
    admin, session = administrator(app)
    path = f"/admin/participants/{state['participant']['id']}/new-draw"
    body = {'event_id':state['event_id'],'draw_version':0,'confirmation':'NEW DRAW'}
    assert post(admin,path,session,body).status_code == 200
    replacement = spin(client,bind(client, state['participant']['id']))
    assert replacement.status_code == 200
    before = allocations(app)
    # Retrying a request whose response was lost must not revoke the replacement.
    assert post(admin,path,session,body).status_code == 409
    assert allocations(app) == before


def test_new_draw_releases_wrong_name_before_spin_and_invalidates_recovery(app):
    wrong_browser = app.test_client(); wrong = bind(wrong_browser)
    other_browser = app.test_client(); other = bind(other_browser)
    spin(other_browser, other)
    before = allocations(app)
    target = wrong['participant']['id']
    actual_id = wrong['participants'][2]['id']
    admin, session = administrator(app)
    recovery = post(admin, f'/admin/participants/{target}/recovery', session,
                    {'event_id': wrong['event_id'], 'confirmation': 'RESET BROWSER LINK'})
    token = recovery.json['recovery_url'].split('#recover=')[1]
    response = post(admin, f'/admin/participants/{target}/new-draw', session,
                    {'event_id': wrong['event_id'], 'draw_version': 0, 'confirmation': 'NEW DRAW'})
    assert response.status_code == 200
    fresh = bootstrap(wrong_browser)
    assert fresh['participant'] is None and not fresh['binding_lost']
    assert not next(p for p in fresh['participants'] if p['id'] == target)['claimed']
    assert allocations(app) == before
    assert bootstrap(other_browser)['participant'] == other['participant']
    assert post(wrong_browser, '/claim', fresh,
                {'event_id': fresh['event_id'], 'participant_id': other['participant']['id']}).status_code == 409
    assert bind(wrong_browser, actual_id)['participant']['id'] == actual_id
    real_owner = app.test_client()
    assert post(real_owner, '/recover', bootstrap(real_owner), {'token': token}).status_code == 410
    assert bind(real_owner, target)['participant']['id'] == target
    assert allocations(app) == before
