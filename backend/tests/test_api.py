import io
import wave
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.models import AudioAnalysis, StageConstraints
from app.planner import _compact_audio_context, _local_plan


def wav_bytes(duration=4, sr=22050):
    t = np.arange(duration * sr) / sr
    y = (.25 * np.sin(2 * np.pi * 220 * t) + .1 * np.sin(2 * np.pi * 2 * t)).astype(np.float32)
    pcm = (np.clip(y, -1, 1) * 32767).astype('<i2')
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(sr); output.writeframes(pcm.tobytes())
    return buffer.getvalue()


def test_model_audio_context_excludes_dense_signal_curves():
    analysis = AudioAnalysis.model_validate({
        'filename': 'test.wav',
        'duration': 10,
        'tempo': 92,
        'beat_times': [0.5, 1.0],
        'onset_envelope': [{'time': 0, 'value': 0.2}],
        'rms_envelope': [{'time': 0, 'value': 0.3}],
        'waveform': [{'time': 0, 'value': 0.4}],
        'sections': [{'start': 0, 'end': 10, 'label': 'A', 'energy': 'medium', 'mean_rms': 0.3, 'interpretation': 'heuristic'}],
        'notes': ['measured'],
    })
    context = _compact_audio_context(analysis)
    assert context['tempo'] == 92
    assert context['sections'][0]['energy'] == 'medium'
    assert 'onset_envelope' not in context
    assert 'rms_envelope' not in context
    assert 'waveform' not in context


def test_real_wav_analysis_and_plan_round_trip():
    client = TestClient(app)
    analyzed = client.post('/api/analyze', files={'file': ('fixture.wav', wav_bytes(), 'audio/wav')})
    assert analyzed.status_code == 200, analyzed.text
    payload = analyzed.json()
    assert payload['analysis']['duration'] >= 3.9
    assert payload['analysis']['rms_envelope']
    planned = client.post('/api/plan', json={'analysis': payload['analysis'], 'constraints': {'dancer_count': 6, 'stage_width': 12, 'stage_depth': 8, 'min_spacing': 1.2, 'max_speed': 3, 'mood': 'precise', 'preferred_formations': ['line', 'circle']}})
    assert planned.status_code == 200, planned.text
    assert planned.json()['validation']['valid'] is True


def test_cached_demo_is_honestly_labeled():
    response = TestClient(app).get('/api/demo')
    assert response.status_code == 200
    assert response.json()['result']['execution_mode'] == 'cached_demo'
    assert 'not a fresh live model run' in response.json()['disclosure']


def test_aistpp_motion_library_lists_and_loads_attributed_clip():
    client = TestClient(app)
    response = client.get('/api/motions')
    assert response.status_code == 200
    catalog = response.json()
    assert catalog['dataset'] == 'FORM attributed motion libraries'
    assert len(catalog['clips']) >= 15
    clip_id = next(clip['id'] for clip in catalog['clips'] if clip['id'].startswith('aistpp-'))
    loaded = client.get(f'/api/motions/{clip_id}')
    assert loaded.status_code == 200
    clip = loaded.json()
    assert clip['frames']
    assert clip['attribution'].endswith('CC BY 4.0')


def test_curated_adavu_reference_is_labeled_without_recognition_claim():
    client = TestClient(app)
    catalog = client.get('/api/motions').json()
    adavu = next(clip for clip in catalog['clips'] if clip['id'] == 'adavu-thattadavu')
    assert adavu['movement_family'] == 'Thattadavu'
    assert adavu['style'] == 'Kalakshetra'
    assert adavu['label_scope'] == 'family_reference'
    loaded = client.get('/api/motions/adavu-thattadavu').json()
    assert loaded['frames']
    assert loaded['duration'] >= 10


def test_motion_palette_cycles_selected_adavus_and_genres_in_user_order():
    demo = TestClient(app).get('/api/demo').json()
    analysis = AudioAnalysis.model_validate(demo['analysis'])
    constraints = StageConstraints(
        preferred_motion_genres=['Thattadavu', 'Nattadavu', 'Middle Hip-Hop'],
        motion_selection_mode='sequence',
    )
    plan = _local_plan(analysis, constraints)
    assert [formation.motion_clip_id for formation in plan.formations[:3]] == [
        'adavu-thattadavu', 'adavu-nattadavu', 'aistpp-mh-ch01',
    ]


def test_every_selected_motion_style_gets_a_phrase_when_palette_exceeds_sections():
    demo = TestClient(app).get('/api/demo').json()
    analysis = AudioAnalysis.model_validate(demo['analysis'])
    selected = ['Thattadavu', 'Nattadavu', 'Kudithu Mettu', 'Break', 'House']
    plan = _local_plan(analysis, StageConstraints(preferred_motion_genres=selected, motion_selection_mode='sequence'))
    assert len(plan.formations) >= len(selected)
    assert [formation.motion_clip_id for formation in plan.formations[:5]] == [
        'adavu-thattadavu', 'adavu-nattadavu', 'adavu-kudithu-mettu',
        'aistpp-br-ch01', 'aistpp-ho-ch01',
    ]


def test_palette_mode_includes_choices_without_treating_click_order_as_sequence():
    demo = TestClient(app).get('/api/demo').json()
    analysis = AudioAnalysis.model_validate(demo['analysis'])
    plan = _local_plan(analysis, StageConstraints(
        preferred_motion_genres=['Middle Hip-Hop', 'Thattadavu'],
        motion_selection_mode='palette',
    ))
    selected_ids = [formation.motion_clip_id for formation in plan.formations[:2]]
    assert selected_ids == ['adavu-thattadavu', 'aistpp-mh-ch01']


def test_manually_edited_plan_can_be_revalidated_without_model_call():
    client = TestClient(app)
    demo = client.get('/api/demo').json()
    valid = client.post('/api/validate', json={
        'plan': demo['result']['plan'],
        'constraints': StageConstraints().model_dump(),
    })
    assert valid.status_code == 200
    assert valid.json()['valid'] is True

    edited = demo['result']['plan']
    edited['formations'][0]['positions']['D1']['x'] = -1
    invalid = client.post('/api/validate', json={
        'plan': edited,
        'constraints': StageConstraints().model_dump(),
    })
    assert invalid.status_code == 200
    assert 'OUT_OF_BOUNDS' in {issue['code'] for issue in invalid.json()['issues']}


def test_direct_formation_edit_generates_complete_geometry():
    response = TestClient(app).post('/api/formations/generate', json={
        'kind': 'diamond',
        'constraints': StageConstraints().model_dump(),
    })
    assert response.status_code == 200
    assert response.json()['kind'] == 'diamond'
    assert set(response.json()['positions']) == {f'D{i}' for i in range(1, 7)}


def test_conversational_revision_requires_live_provider(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    demo = TestClient(app).get('/api/demo').json()
    response = TestClient(app).post('/api/revise', json={
        'analysis': demo['analysis'],
        'constraints': StageConstraints().model_dump(),
        'current_plan': demo['result']['plan'],
        'instruction': 'Make the middle phrase more dramatic.',
    })
    assert response.status_code == 503
    assert 'live AI provider' in response.json()['detail']


def test_ensemble_diagnosis_rejects_non_video_upload():
    response = TestClient(app).post('/api/analyze-ensemble', data={
        'expected_dancers': '6',
        'beat_times': '[]',
    }, files={'file': ('notes.txt', b'not video', 'text/plain')})
    assert response.status_code == 415
