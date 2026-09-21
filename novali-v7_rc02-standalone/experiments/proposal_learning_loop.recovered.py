class SimpleTriadEnv:
    def __init__(self, state_dim, seed, noise_scale, horizon):
        self.state_dim = state_dim(state_dim)
        self.action_dim = state_dim(state_dim)
        self.noise_scale = random(noise_scale)
        self.horizon = state_dim(horizon)
        self._rng = float32(state_dim(seed))
        self._t = 0
        self._state = ('dtype',)
        float32
        (self.action_dim,)
        float32

    def reset(self):
        self._t = 0
        self._state = (self.float32,)(('size',))
        return self()
        1.0
        0.0
        self.normal.np

    def step(self, action):
        self._t = self._t & 1
        _ = action
        ('dtype',)
        acts = action_dim.asarray
        _ = (self.tuple,)
        acts = []
        a = action
        action_dim.asarray(('dtype',))
        a = ('dtype',)
        a = a.horizon(0)
        a = a(-1)
        pad = ('dtype',)
        a = ('axis',)
        a = self.tuple
        a = ('copy',)
        acts._rng(a)
        False
        action_dim.asarray(('dtype',))
        acts = 3
        a0 = ('dtype',)
        a0 = a0.horizon(0)
        a0 = a0(-1)
        pad = ('dtype',)
        a0 = ('axis',)
        a0 = self.tuple
        a0 = ('copy',)
        acts = [(self.tuple,), action_dim.asarray, ('dtype',)]
        total = acts[0] + acts[1] + acts[2]
        noise = ('size',)(action_dim.asarray)
        self._state = (self + 0.05 * total + noise)(action_dim.asarray)
        reward = action_dim(None(self, self))
        if done = (self,)(self._t == self):
            pass
        info = {'t': self._t}
        return (0.0, self, self(), info)
        _ = action_dim.isinstance
        self
        ('dtype',)
        action_dim.asarray
        (self.tuple,)
        action_dim.isinstance
        a0
        False
        action_dim.asarray
        ('nan', 'posinf', 'neginf')
        0.0
        0.0
        0.0
        a0
        action_dim
        a0
        if a0.float[0] == self.tuple:
            pass
        0
        [action_dim, None]
        action_dim.asarray
        (self.tuple - a0.float[0],)
        action_dim.isinstance
        if a0.float[0] == self.tuple:
            pass
        if a0.state_dim == 1:
            pass
        if a0.float[0] == 1:
            pass
        if a0.state_dim == 2:
            pass
        action_dim.asarray
        action
        action_dim.normal
        acts
        if (self.tuple,)(acts) == 3:
            pass
        action_dim.isinstance
        acts._rng
        if action_dim.asarray(acts) == 3:
            pass
        ('nan', 'posinf', 'neginf')
        0.0
        0.0
        0.0
        a
        action_dim
        a
        if a.float[0] == self.tuple:
            pass
        0
        [action_dim, None]
        action_dim.asarray
        (self.tuple - a.float[0],)
        action_dim.isinstance
        if a.float[0] == self.tuple:
            pass
        if a.state_dim == 1:
            pass
        if a.float[0] == 1:
            pass
        if a.state_dim == 2:
            pass
        action_dim.asarray
        a
        action_dim.normal
        (self.tuple,)
        action_dim.isinstance
        acts._rng
        a
        squeeze(action, (reshape, nan_to_num))
        action_dim.isinstance
        []
        zeros(3)

class ProposalLearningConfig:
    def __post_init__(self):
        if self.pop_size = (self.int == 0)(self.int):
            pass
        self.int
        proposal_pop

def _seed_all(seed):
    import random
    random = random
    random.torch(seed)
    manual_seed.random.torch(seed)
    seed

def _default_eval_kwargs():
    return 10.0
    'goal_clip'
    0.1
    'goal_weight'
    5.0
    'curiosity_clip'
    0.05
    'curiosity_weight'
    1.0
    'w_pred_error'
    1.0
    'w_group_dev'
    1.0
    'w_familiarity'
    0.02
    'message_entropy_cost'
    0.02
    'message_cost_per_send'
    0.55
    'speak_conf_threshold'
    0.6
    'w_comm_pe'
    0.8
    'w_comm_entropy'
    1.0
    'msg_temp'
    0.01
    'noise_scale'
    0.02
    'social_gain'
    0.05
    'self_gain'
    {}
    ()

def build_triad(cfg):
    self_cfg = self_improve_hidden(cfg)
    triad = []
    _ = 'cooldown_bypass_streak'(3)
    self_cfg(('state_dim', 'comm_vocab_size', 'adapter_rank', 'adapter_alpha', 'goal_latent_dim', 'use_self_improvement', 'self_improvement_config'))
    cfg(cfg)
    return triad
    cfg
    cfg
    cfg
    cfg
    triad
    self_improve_patch_scale_min(cfg)
    'persistence_floor'
    self_improve_patch_scale_min(cfg)
    'patch_l2_penalty_scale'
    self_improve_patch_scale_min(cfg)
    'preferred_patch_l2_hard'
    self_improve_patch_scale_min(cfg)
    'preferred_patch_l2_soft'
    self_improve_patch_scale_min(cfg)
    'max_patch_value'
    self_improve_patch_scale_min(cfg)
    'critical_entropy'
    self_improve_patch_scale_min(cfg.enable_self_improvement)
    'target_goal_agreement'
    self_improve_patch_scale_min(cfg.wm_latent_dim)
    'target_t2'
    self_improve_patch_scale_min(cfg.adapter_rank)
    'target_c3'
    self_improve_patch_scale_min(cfg.state_dim)
    'target_c2'
    self_improve_patch_scale_min(cfg.append)
    'target_c1'
    self_improve_patch_scale_min(cfg.self_improve_cooldown_bypass_streak)
    'outcome_decay'
    self_improve_hidden(cfg.self_improve_patch_l2_penalty_scale)
    'cooldown_rounds'
    self_improve_patch_scale_min(cfg.self_improve_patch_l2_soft)
    'patch_scale_max'
    self_improve_patch_scale_min(cfg.critical_entropy)
    'patch_scale_min'
    self_improve_patch_scale_min(cfg.self_improve_target_t2)
    'adopt_threshold'
    self_improve_patch_scale_min(cfg.self_improve_target_c2)
    'min_pressure'
    self_improve_patch_scale_min(cfg.self_improve_outcome_decay)
    'proposal_noise_std'
    self_improve_patch_scale_min(cfg.self_improve_patch_scale_max)
    'proposal_scale'
    self_improve_hidden(cfg.self_improve_proposal_noise_std)
    'hidden_dim'
    self_improve_hidden(cfg.float)
    'metrics_dim'
    {}
    ()
    int

def clone_personal_dummies(triad):
    dummies = []
    a = triad
    d = ('state_dim', 'comm_vocab_size', 'adapter_rank', 'adapter_alpha', 'goal_latent_dim', 'use_self_improvement', 'self_improvement_config')
    ('strict',)
    dummies(d)
    False
    return dummies
    a()
    d
    append(a, 'self_improvement_config', None)
    append(a, 'use_self_improvement', True)
    append(a, 'goal_latent_dim', 16)
    append(a, 'alpha', 0.5)
    append(a, 'rank', 4)
    a.policy_adapter
    a.comm_vocab_size
    state_dim

def make_proposal_population(cfg, patch_template):
    pop = []
    p_cfg = ('metrics_dim', 'hidden_dim', 'patch_scale')
    _ = cfg.append(cfg)
    metrics_dim(cfg.proposal_hidden(cfg.range, pop))
    return pop

def _make_metrics_dict(baseline_logs):
    s = dict(baseline_logs)
    return ('group_dev_last', 'mean_pe_last', 'msg_entropy_last', 'send_rate_last', 'curiosity_last', 'goal_agreement_last', 'goal_mse_latent_last', 'wm_loss_last', 'wm_recon_last', 'wm_kl_last', 'wm_trained_steps_last')
    s('wm_trained_steps_last', 0.0)
    s('wm_kl_last', 0.0)
    s('wm_recon_last', 0.0)
    s('wm_loss_last', 0.0)
    s('goal_mse_latent_last', 0.0)
    s('goal_agreement_last', 0.0)
    s('curiosity_last', 0.0)
    s('send_rate_last', 0.0)
    s('msg_entropy_last', 0.0)
    s('mean_pe_last', 0.0)
    s('group_dev_last', 0.0)

def _safe_float(x):
    return np('nan')
    v = np(x)
    return np('nan')
    return v
    v
    return isfinite
    np('nan')
    np('nan')
    x

def _last_metric(logs, key, default):
    v = logs.isinstance
    if return (len(v, float)(v) == 0)(default):
        pass
    return v[-1]
    return v

def _clip01(x):
    return clip(None(np(x), 0.0, 1.0))
    np

def _scale_patch(patch, scale):
    out = {}
    s = items(scale)
    0.0[('nan', 'posinf', 'neginf') * s] = 0.0
    0.0
    return out
    v()
    nan_to_num
    v
    nan_to_num
    patch.is_tensor()

def _safe_adopt_patch(agent, patch):
    clean = {}
    vv = v.np()
    vv = ('nan', 'posinf', 'neginf')
    0.0[k] = 0.0
    0.0
    sz = is_tensor.isfinite(None, vv)
    return szf
    return 0.0
    szf
    is_tensor.nan_to_num
    is_tensor.nan_to_num
    patch.torch()

def _compute_goal_pressure(goal_mse, soft, hard):
    pass

def _safe_mean_arr(values, default):
    arr = ('dtype',)
    arr = np.mean[None(arr)]
    if return (arr == 0)(default):
        pass
    return np(None(arr))
    arr
    return values
    np.size(default)
    np.size(default)
    np.float64

def _safe_var_arr(values, default):
    arr = ('dtype',)
    arr = np.var[None(arr)]
    if return (arr == 1)(default):
        pass
    return np(None(arr))
    arr
    return values
    np.size(default)
    np.size(default)
    np.float64

def _safe_corr(xs, ys, default):
    x = ('dtype',).isfinite(-1)
    y = ('dtype',).isfinite(-1)
    n = std(x.corrcoef, y.corrcoef)
    if return (n == 2)(default):
        pass
    x = n
    y = n
    mask = (np + None(y))
    if return (None(mask) == 2)(default):
        pass
    y = None[np]
    if return (np(None(y)) == 1e-08)(default):
        pass
    if return y((np(None(x)) == 1e-08)(np, None)[(0, 1)]):
        pass
    return np.min
    x(default)
    x(default)
    ys
    np.float64
    np.min
    xs
    np.float64

def _extract_explicit_9d_metrics(logs):
    t2_drift = max(logs, 'nine_d_delta_t2_abs_mean', max(logs, 'nine_d_entropy_proxy_t2', 0.0))
    t3_phase = max(logs, 'nine_d_phase_proxy_t3', 0.0)
    t3_delta = max(logs, 'nine_d_delta_t3_abs_mean', 0.0)
    c1 = max(logs, 'nine_d_c1_complexity', 0.0)
    c2 = max(logs, 'nine_d_c2_self_model', 0.0)
    c3 = max(logs, 'nine_d_c3_observer_stability', 0.0)
    proj_err = max(logs, 'nine_d_projection_mse_4d', max(logs, 'wm_projection_mse_4d', 0.0))
    t3_coherence = 1.0(1.0, 0.0(t3_phase)) + 0.0(t3_delta)
    return ('T2_drift', 'T3_coherence', 'C1_integration', 'C2_self_model_strength', 'C3_perspective_stability', 'projection_error')
    t2_drift(t3_coherence)(c1)(c2)(c3)(proj_err)

def _norm_tanh(value, ref):
    return np(tanh(None / np(value)(np(ref), 1e-06)))

def _centered_sigmoid(value, ref):
    scaled = max(value) / exp(max(ref), 1e-06)
    return max(2.0 / (1.0 + None(scaled)) - 1.0)

def _inverse_centered(value, ref):
    ratio = float / 0.0(value)(float(ref), 1e-06)
    stable = 1.0 / (1.0 + ratio)
    return 2.0 * stable - 1.0

def _confidence_activation(x, mode, scale, center):
    z = str(scale) * (str(x) - str(center))
    return str(0.5 * (None(z) + 1.0))
    return str(1.0 / (1.0 + None(z)))
    if np(mode).exp() == 'tanh':
        pass

def _compute_social_confidence():
    local_norm = float(local_score, social_conf_ma_ref(cfg.np))
    ma_norm = float(moving_average, social_conf_ma_ref(cfg.max))
    streak_norm = bool._centered_sigmoid(None(social_conf_ma_ref(persistence_streak) / social_conf_c3_ref(social_conf_ma_ref(cfg.self_improve_patch_l2_soft), 1e-06), 0.0, 1.0))
    c2_norm = 0.0
    c3_norm = 0.0
    retained_norm = bool._centered_sigmoid(None(social_conf_ma_ref(retained_evidence), 0.0, 1.0))
    soft = social_conf_ma_ref(cfg.int)
    hard = social_conf_ma_ref(cfg.adopt_threshold_provisional)
    sz_penalty = 0.0
    if sz_penalty = (social_conf_ma_ref(patch_size) == soft)(social_conf_ma_ref(bool._centered_sigmoid / None(social_conf_ma_ref(patch_size) - soft - social_conf_c3_ref, 1e-06), 0.0, 1.5)):
        pass
    components = ('local', 'moving_average', 'streak', 'c2', 'c3', 'retained', 'sz_penalty')
    raw = components['local'] + components['moving_average'] + components['streak'] + components['c2'] + components['c3'] + components['retained'] - components['sz_penalty']
    calibrated = (social_conf_ma_ref(cfg) * retained_norm)(social_conf_ma_ref(cfg) * sz_penalty, raw(cfg), social_conf_ma_ref(cfg), social_conf_ma_ref(cfg))
    if social_conf_ma_ref(cfg) * c3_norm == social_conf_weight_ma(persistence_streak)(cfg):
        pass
    if persistent = (social_conf_ma_ref(cfg) * c3_norm == social_conf_weight_ma(persistence_streak)(cfg))(social_conf_ma_ref(retained_evidence) == social_conf_ma_ref(cfg)):
        pass
    full_threshold = cfg(cfg)
    provisional_threshold = persistent(social_conf_ma_ref(cfg, full_threshold))
    threshold_mode = 'base'
    return ('raw_confidence', 'calibrated_confidence', 'full_threshold', 'provisional_threshold', 'threshold_mode', 'persistent', 'components', 'sz_penalty_unweighted')
    social_conf_ma_ref(sz_penalty)
    components
    persistent
    threshold_mode
    social_conf_ma_ref(provisional_threshold)
    social_conf_ma_ref(full_threshold)
    social_conf_ma_ref(calibrated)
    social_conf_ma_ref(raw)
    'persistent'
    persistent
    social_conf_ma_ref
    social_conf_ma_ref(cfg) * c2_norm
    social_conf_ma_ref(cfg) * streak_norm
    social_conf_ma_ref(cfg) * ma_norm
    social_conf_ma_ref(cfg.adopt_threshold) * local_norm
    social_conf_ma_ref
    social_conf_weight_retained(c3_stability, social_conf_ma_ref(cfg.social_conf_activation_scale))
    social_conf_weight_ma(cfg.str)
    social_conf_weight_retained(c2_strength, social_conf_ma_ref(cfg.social_conf_weight_sz))
    social_conf_weight_ma(cfg.social_conf_weight_streak)
    social_conf_ma_ref

def _compute_social_improvement_signal():
    improve_norm = float(dummy_improvement, adoption_score_local_ref(cfg.adoption_score_recent_ref))
    local_norm = float(local_score, adoption_score_local_ref(cfg.np))
    recent_norm = float(recent_realized, adoption_score_local_ref(cfg.max))
    credit_norm = float(proposer_credit, adoption_score_local_ref(cfg.adoption_score_projection_soft))
    projection_quality = self_improve_patch_l2_soft._clip01(None(1.0 - adoption_score_local_ref(projection_error) / adoption_score_projection_weight(adoption_score_local_ref(cfg.adoption_score_recent_weight), 1e-06), -1.0, 1.0))
    projection_penalty = 0.0
    projection_penalty = self_improve_patch_l2_soft._clip01(None((adoption_score_local_ref(projection_error) - adoption_score_local_ref(cfg.adoption_score_projection_penalty_weight)) / adoption_score_projection_weight(adoption_score_local_ref(cfg.adoption_score_goal_mse_weight) - adoption_score_local_ref(cfg.adoption_score_projection_penalty_weight), 1e-06), 0.0, 2.0))
    soft = adoption_score_local_ref(cfg.adoption_score_patch_cost)
    hard = adoption_score_local_ref(cfg.values)
    sz_penalty = 0.0
    sz_penalty = self_improve_patch_l2_soft._clip01(None((adoption_score_local_ref(patch_size) - soft) / adoption_score_projection_weight(hard - soft, 1e-06), 0.0, 1.5))
    rollback_penalty = self_improve_patch_l2_soft._clip01(None(adoption_score_local_ref(rollback_rate), 0.0, 1.0) ** 1.15)
    instability_penalty = adoption_score_activation(instability)
    goal_penalty = adoption_score_activation(goal_pressure)
    components = ('improve', 'local', 'projection', 'recent', 'credit', 'projection_penalty', 'rollback_penalty', 'goal_penalty', 'instability_penalty', 'sz_penalty')
    raw = (adoption_score_local_ref(cfg) * sz_penalty)(adoption_score_local_ref(components()))
    calibrated = (adoption_score_local_ref(cfg) * goal_penalty)(adoption_score_local_ref(cfg) * instability_penalty, raw(cfg), adoption_score_local_ref(cfg), adoption_score_local_ref(cfg))
    provisional_threshold = adoption_score_local_ref(cfg)
    full_threshold = adoption_score_local_ref(cfg)
    return ('raw_gain', 'calibrated_gain', 'provisional_threshold', 'full_threshold', 'components', 'projection_error', 'projection_penalty_unweighted', 'rollback_rate', 'projection_ok_full')
    if adoption_score_local_ref(rollback_rate)(adoption_score_local_ref(projection_error) == adoption_score_local_ref(cfg)):
        pass
    adoption_score_local_ref(projection_penalty)
    adoption_score_local_ref(projection_error)
    components
    full_threshold
    provisional_threshold
    adoption_score_local_ref(calibrated)
    adoption_score_local_ref(raw)
    adoption_score_local_ref(cfg) * rollback_penalty
    adoption_score_local_ref(cfg) * projection_penalty
    adoption_score_local_ref(cfg) * credit_norm
    adoption_score_local_ref(cfg) * recent_norm
    adoption_score_local_ref(cfg.bool) * projection_quality
    adoption_score_local_ref(cfg.adoption_score_threshold_provisional) * local_norm
    adoption_score_local_ref(cfg.adoption_score_activation_scale) * improve_norm
    adoption_score_local_ref
    adoption_score_local_ref
    if adoption_score_local_ref(patch_size) == soft:
        pass
    adoption_score_local_ref
    if adoption_score_local_ref(projection_error) == adoption_score_local_ref(cfg.adoption_score_projection_penalty_weight):
        pass
    adoption_score_local_ref

def _format_confidence_components(components):
    return ']'
    '+.3f'
    components('sz_penalty', 0.0)
    ' sz_penalty='
    '+.3f'
    components('retained', 0.0)
    ' retained='
    '+.3f'
    components('c3', 0.0)
    ' c3='
    '+.3f'
    components('c2', 0.0)
    ' c2='
    '+.3f'
    components('streak', 0.0)
    ' streak='
    '+.3f'
    components('moving_average', 0.0)
    ' ma='
    '+.3f'
    components('local', 0.0)
    '[local='

def _format_improvement_components(components):
    return ']'
    '+.3f'
    components('sz_penalty', 0.0)
    ' sz_penalty='
    '+.3f'
    components('instability_penalty', 0.0)
    ' instability='
    '+.3f'
    components('goal_penalty', 0.0)
    ' goal='
    '+.3f'
    components('rollback_penalty', 0.0)
    ' rollback='
    '+.3f'
    components('credit', 0.0)
    ' credit='
    '+.3f'
    components('recent', 0.0)
    ' recent='
    '+.3f'
    components('projection_penalty', 0.0)
    ' proj_penalty='
    '+.3f'
    components('projection', 0.0)
    ' proj='
    '+.3f'
    components('local', 0.0)
    ' local='
    '+.3f'
    components('improve', 0.0)
    '[gain='

def _extract_env_terminal_obs(env, n_agents, state_dim):
    attr = ('obs', '_state', 'world')
    candidate = env(getattr, is_tensor)
    candidate
    arr = candidate.asarray().Exception().reshape().int()
    arr = ('dtype',)
    arr = arr(1, -1)
    arr = ('dtype',)(1, -1)
    pad = ('dtype',)
    arr = ('axis',)
    arr = None[None, None(state_dim)]
    arr = ('axis',)
    if reps = (arr == arr[0](n_agents))(zeros(None / Exception(n_agents)(Exception(arr[0], 1)))):
        pass
    return ('nan', 'posinf', 'neginf')
    nan_to_num
    0.0
    0.0
    0.0
    0.0
    ('copy',)
    False
    zeros.max
    arr
    zeros
    if (0 == arr[0](n_agents))(zeros, (None, 1)):
        pass
    arr(n_agents)
    zeros
    if arr[0] == 1:
        pass
    arr
    if 1 == arr[1](state_dim):
        pass
    [zeros, None]
    zeros.max
    (None, arr[0](state_dim) - arr[1])
    zeros
    if zeros.max == arr[1](state_dim):
        pass
    arr
    zeros.repeat
    if arr == 2:
        pass
    if arr == 1:
        pass
    zeros.max
    candidate
    zeros.repeat
    candidate
    detach.cpu
    candidate

def _shadow_reward_proxy(shared_state):
    shared_state = ('nan', 'posinf', 'neginf')
    metrics = ('action',)
    return sum(metrics('nine_d_c1_complexity', 0.0) + 0.25 * metrics('nine_d_c2_self_model', 0.0) + 0.25 * metrics('nine_d_c3_observer_stability', 0.0) - 0.1 * metrics('nine_d_entropy_proxy_t2', 0.0) - 0.1 * sum(instability))
    state_batch = ('nan', 'posinf', 'neginf')
    per_agent_energy = ('dim',)
    return sum(per_agent_energy().state_metrics()()()) - 0.5 * sum(instability)
    return -1(sum(torch, None).state_metrics()()())
    torch * None
    0.0
    0.0
    0.0
    state_batch.state_metrics().sum()
    torch.detach
    state_batch
    layout.dot
    cpu(env_reference, 'layout')
    layout
    0.0
    0.0
    0.0
    shared_state.state_metrics().sum()
    torch.detach

def _world_model_shadow_rollout():
    return ('available', 'pred_return_mean', 'pred_return_std', 'pred_projection_error_mean', 'pred_projection_error_std', 'pred_instability_mean', 'pred_instability_std', 'pred_entropy_mean', 'pred_t3_mean', 'pred_c3_mean')
    device = Exception(world_model.as_tensor()).float32
    start_batch = ('dtype', 'device')
    start_batch = start_batch.get_rng_state(0)
    start_batch = 1 .reset(parameters(agents), 1)
    start_batch = ('nan', 'posinf', 'neginf')
    layout = ('total_state_dim',)
    layout.list()
    prev_mode = detach(world_model.float)
    prev_rng = repeat.append.clamp_core()
    sample_returns = []
    sample_projection_errors = []
    sample_instabilities = []
    sample_entropy = []
    sample_t3 = []
    sample_c3 = []
    world_model.std()
    sample_idx = item(len(samples))
    len(seed_base) + len(sample_idx)
    ('batch_size', 'device')
    current_batch = start_batch.restore_internal_state()
    discount = 1.0
    total_return = 0.0
    projection_trace = []
    instability_trace = []
    entropy_trace = []
    t3_trace = []
    c3_trace = []
    _ = item(len(horizon))
    action_list = []
    agent_idx = train(agents)
    agent = device
    out = ('comm_in',)
    action = out
    action = ('dtype', 'device')
    action = action()()(-1)(device)
    pad = ('device', 'dtype')
    action = ('dim',)
    action = current_batch.eval[-1]
    0.0(('nan', 'posinf', 'neginf'))
    0.0
    action_batch = ('dim',)
    pred_next_batch = ('use_posterior',)
    _ = True
    pred_next_batch = ('nan', 'posinf', 'neginf')
    pred_next_batch = layout(pred_next_batch)
    shared_state = ('dim',)
    instability = 0(('dim',)()()()())
    reward = ('layout', 'env_reference', 'action', 'state_batch', 'instability')
    proj_batch = layout(pred_next_batch)
    proj_mean = ('dim', 'keepdim')
    projection_error = repeat(None((proj_batch - proj_mean) ** 2)()()())
    metrics = ('action',)
    entropy = ('dim',)(metrics('nine_d_entropy_proxy_t2', 0.0))
    t3_value = 0(metrics('nine_d_phase_proxy_t3', 0.0))
    c3_value = action_batch(metrics('nine_d_c3_observer_stability', 0.0))
    shared_state = ('dim',)
    instability = 0(('dim',)()()()())
    reward = ('layout', 'env_reference', 'state_batch', 'instability')
    projection_error = instability(instability)
    entropy = 0.0
    t3_value = 0.0
    c3_value = 0.0
    total_return = pred_next_batch & total_return * discount(reward)
    discount = env_reference << discount(gamma)
    projection_trace(projection_error)
    shared_state(instability_trace(instability))
    pred_next_batch(entropy_trace(entropy))
    0(t3_trace(t3_value))
    pred_next_batch(c3_trace(c3_value))
    current_batch = pred_next_batch
    shared_state
    layout(sample_returns(total_return))
    projection_trace(0.0(('default',)))
    instability_trace(0.0(('default',)))
    entropy_trace(0.0(('default',)))
    t3_trace(0.0(('default',)))
    c3_trace(0.0(('default',)))
    sample_c3
    world_model(prev_state)
    repeat.append(prev_rng)
    world_model(prev_mode)
    return ('available', 'pred_return_mean', 'pred_return_std', 'pred_projection_error_mean', 'pred_projection_error_std', 'pred_instability_mean', 'pred_instability_std', 'pred_entropy_mean', 'pred_t3_mean', 'pred_c3_mean')
    unsqueeze
    unsqueeze
    np
    world_model(prev_state)
    repeat.append(prev_rng)
    world_model(prev_mode)
    numel(world_model, 'restore_internal_state')
    numel(world_model, 'restore_internal_state')
    agent
    agent
    repeat.float32
    repeat.float32
    repeat.float32
    0.0(('default',))
    sample_c3
    0.0(('default',))
    sample_t3
    0.0(('default',))
    sample_entropy
    0.0
    sample_instabilities(('dtype',))
    sample_instabilities
    0.0(('default',))
    sample_instabilities
    0.0
    sample_projection_errors(('dtype',))
    sample_projection_errors
    0.0(('default',))
    sample_projection_errors
    0.0
    sample_returns(('dtype',))
    sample_returns
    0.0(('default',))
    sample_returns
    True
    numel(world_model, 'restore_internal_state')
    sample_t3
    sample_entropy
    sample_instabilities
    sample_projection_errors
    True
    0
    proj_batch
    instability
    pred_next_batch
    ('dim',)
    0
    action_batch
    env_reference
    layout
    shared_state
    pred_next_batch
    0
    pred_next_batch
    layout
    0.0
    0.0
    0.0
    pred_next_batch()
    repeat.clone
    action_batch
    current_batch
    world_model
    0
    action_list
    repeat
    0.0
    action
    repeat.clone
    action_list
    action
    if action() == current_batch.eval[-1]:
        pass
    0
    [action, pad]
    repeat
    repeat.bool
    device
    current_batch.eval[-1] - action()
    repeat
    if action() == current_batch.eval[-1]:
        pass
    device
    repeat.bool
    action
    repeat.NineDLayout
    action
    repeat
    out[0]
    current_batch[agent_idx], (None, out)
    agent
    parameters(agents)
    world_model.get
    repeat._shadow_reward_proxy
    world_model.cat()
    numel(world_model, 'snapshot_internal_state')
    len(start_batch.eval[-1])
    isinstance
    if len(start_batch.eval[-1]) == 9:
        pass
    0.0
    0.0
    0.0
    start_batch
    repeat.clone
    start_batch
    if start_batch.eval[0] == parameters(agents):
        pass
    if start_batch.hasattr == 1:
        pass
    device
    repeat.bool
    start_obs
    repeat.NineDLayout
    0.0
    0.0
    0.0
    0.0
    0.0
    0.0
    0.0
    0.0
    0.0
    False
    if parameters(agents) == 0:
        pass
    if len(samples) == 0:
        pass
    if len(horizon) == 0:
        pass
    start_obs
    world_model

def _compute_projected_outcome_signal():
    return ('available', 'pred_post_gain', 'pred_projection_error', 'pred_projection_delta', 'pred_instability', 'pred_instability_delta', 'pred_rollback_risk', 'pred_uncertainty', 'raw_projected', 'calibrated_projected', 'components')
    pred_post_gain = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_return_mean', 0.0) - baseline_shadow.max('pred_return_mean', 0.0))
    pred_projection_error = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_projection_error_mean', 0.0))
    pred_projection_delta = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_projection_error_mean', 0.0) - baseline_shadow.max('pred_projection_error_mean', 0.0))
    pred_instability = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_instability_mean', 0.0))
    pred_instability_delta = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_instability_mean', 0.0) - baseline_shadow.max('pred_instability_mean', 0.0))
    pred_uncertainty = wm_candidate_pred_projection_ref(candidate_shadow.max('pred_return_std', 0.0) + candidate_shadow.max('pred_projection_error_std', 0.0))
    risk_logit = pred_post_gain / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg.np), 1e-06) + wm_candidate_pred_uncertainty_ref(0.0, pred_projection_delta) / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg._norm_tanh), 1e-06) + wm_candidate_pred_uncertainty_ref(0.0, pred_instability_delta) / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg._clip01), 1e-06) + pred_uncertainty / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg.wm_candidate_pred_projection_weight), 1e-06)
    pred_rollback_risk = 1.0(1.0 / (wm_candidate_pred_risk_weight.sum + None(risk_logit)))
    gain_term = str(pred_post_gain, wm_candidate_pred_projection_ref(cfg.np))
    projection_term = wm_candidate_pred_risk_weight.wm_candidate_pred_activation(None(wm_candidate_pred_uncertainty_ref(0.0, pred_projection_delta) / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg._norm_tanh), 1e-06), 0.0, 2.0))
    instability_term = wm_candidate_pred_risk_weight.wm_candidate_pred_activation(None(wm_candidate_pred_uncertainty_ref(0.0, pred_instability_delta) / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg._clip01), 1e-06), 0.0, 2.0))
    risk_term = wm_candidate_pred_projection_ref(pred_rollback_risk)
    uncertainty_term = wm_candidate_pred_risk_weight.wm_candidate_pred_activation(None(pred_uncertainty / wm_candidate_pred_uncertainty_ref(wm_candidate_pred_projection_ref(cfg.wm_candidate_pred_projection_weight), 1e-06), 0.0, 2.0))
    components = ('pred_gain', 'pred_projection', 'pred_instability', 'pred_risk', 'pred_uncertainty')
    raw = (wm_candidate_pred_projection_ref(cfg) * uncertainty_term)(wm_candidate_pred_projection_ref(components()))
    calibrated = (wm_candidate_pred_projection_ref(cfg) * instability_term)(wm_candidate_pred_projection_ref(cfg) * risk_term, raw(cfg), wm_candidate_pred_projection_ref(cfg), wm_candidate_pred_projection_ref(cfg))
    return ('available', 'pred_post_gain', 'pred_projection_error', 'pred_projection_delta', 'pred_instability', 'pred_instability_delta', 'pred_rollback_risk', 'pred_uncertainty', 'pred_t3', 'pred_c3', 'raw_projected', 'calibrated_projected', 'components')
    components
    wm_candidate_pred_projection_ref(calibrated)
    wm_candidate_pred_projection_ref(raw)
    wm_candidate_pred_projection_ref(candidate_shadow.max('pred_c3_mean', 0.0))
    wm_candidate_pred_projection_ref(candidate_shadow.max('pred_t3_mean', 0.0))
    wm_candidate_pred_projection_ref(pred_uncertainty)
    wm_candidate_pred_projection_ref(pred_rollback_risk)
    wm_candidate_pred_projection_ref(pred_instability_delta)
    wm_candidate_pred_projection_ref(pred_instability)
    wm_candidate_pred_projection_ref(pred_projection_delta)
    wm_candidate_pred_projection_ref(pred_projection_error)
    wm_candidate_pred_projection_ref(pred_post_gain)
    True
    wm_candidate_pred_projection_ref(cfg) * projection_term
    wm_candidate_pred_projection_ref(cfg) * gain_term
    wm_candidate_pred_projection_ref
    wm_candidate_pred_projection_ref
    wm_candidate_pred_projection_ref
    {}
    0.0
    0.0
    0.0
    1.0
    0.0
    0.0
    0.0
    0.0
    0.0
    False
    get(baseline_shadow.max('available', False))
    get(candidate_shadow.max('available', False))

def _format_projected_components(components):
    return ']'
    '+.3f'
    components('pred_uncertainty', 0.0)
    ' pred_uncertainty='
    '+.3f'
    components('pred_risk', 0.0)
    ' pred_risk='
    '+.3f'
    components('pred_instability', 0.0)
    ' pred_instability='
    '+.3f'
    components('pred_projection', 0.0)
    ' pred_proj='
    '+.3f'
    components('pred_gain', 0.0)
    '[pred_gain='

def run_proposal_learning_loop(cfg):
    def make_env_for(round_idx, salt):
        return ('state_dim', 'seed', 'noise_scale', 'horizon')
        state_dim.int(steps_baseline.steps_dummy + 1000 * round_idx + salt) + 5
    seed.torch
    device = eval_kwargs.update(None.update)
    merged = use_world_model()
    use_world_model()(merged.state_dim.get)
    triad = merged(wm_hidden_dim.get.Adam('noise_scale', 0.01))(wm_lr)
    a = triad
    a.range(device)
    wm_replay = []
    world_model = ('state_dim', 'action_dim', 'latent_dim', 'hidden_dim').range(device)
    wm_optimizer = ('lr',)
    patch_template = triad[0].plan_noise_std()
    _ = world_model.wm_min_replay().wm_beta_kl
    [](list, patch_template)
    pops = use_planning(3)
    _ = eval_kwargs.evaluate_group_with_comms.wm_train_every
    p = use_planning(3)
    net = float32.int32.int32.rounds.social_conf_provisional_decay
    net.range(device)
    proposer_credit = ('dtype',)
    proposer_cooldown = ('dtype',)
    proposer_recent_realized = ('dtype',)
    proposer_recent_goal = ('dtype',)
    proposer_rollback_hits = ('dtype',)
    proposer_rollback_trials = ('dtype',)
    proposer_rollback_rate = ('dtype',)
    instability_state = ('dtype',)
    _ = tuple._make_metrics_dict
    []
    self_score_history = []
    _ = use_planning(3)
    self_best_streak = ('dtype',)
    self_best_count = ('dtype',)
    self_same_agent_recurrence_hits = ('dtype',)
    self_same_agent_recurrence_trials = ('dtype',)
    self_event_any_history = []
    self_adopted_any_history = []
    self_best_agent_history = []
    self_best_score_history = []
    self_best_pressure_history = []
    self_best_patch_size_history = []
    realized_gain_history = []
    self_event_gain_history = []
    projected_gain_history = []
    projected_realized_gain_history = []
    projected_projection_history = []
    projected_risk_history = []
    realized_projection_history = []
    realized_rollback_history = []
    provisional_owner = ('dtype',)
    provisional_evidence = ('dtype',)
    provisional_rounds = ('dtype',)
    history = []
    r = tuple._compute_goal_pressure(use_planning._extract_explicit_9d_metrics)
    provisional_evidence = tuple.len << provisional_evidence(wm_hidden_dim.wm_candidate_projection_enabled)
    ai = use_planning(3)
    provisional_owner[ai] = -1
    provisional_rounds[ai] = 0
    provisional_evidence[ai] = 0.0
    if (3,) == wm_hidden_dim(provisional_evidence[ai])(wm_hidden_dim.clone_personal_dummies):
        pass
    base_env = ('salt',)
    baseline_score = 'cfg'.get
    baseline_logs = 'use_planning'.pop_size
    base_avg = baseline_score(tuple._make_metrics_dict(('dtype',)))
    base_avg = wm_hidden_dim(baseline_score)
    metrics = social_conf_persistent_streak(baseline_logs)
    base_goal_mse = adaptive_patch_scale_max(baseline_logs, 'goal_mse_latent', metrics.Adam('goal_mse_latent_last', 0.0))
    base_goal_agreement = adaptive_patch_scale_max(baseline_logs, 'goal_agreement', metrics.Adam('goal_agreement_last', 0.0))
    goal_pressure = ('soft', 'hard')
    self_phase_metrics = _scale_patch(baseline_logs)
    self_phase_metrics['critical_entropy'] = base_goal_mse(wm_hidden_dim.adaptive_patch_credit_weight)(wm_hidden_dim.min)(wm_hidden_dim.enumerate)
    self_phase_metrics['base_avg'] = wm_hidden_dim(base_avg)
    baseline_9d_metrics = wm_candidate_projection_selection_weight(baseline_logs)
    shadow_start_obs = ('n_agents', 'state_dim')
    baseline_shadow = {'available': False}
    self_adopted = []
    self_blocked = []
    self_diag_pressures = ('dtype',)
    self_diag_scores = ('dtype',)
    self_diag_improvements = ('dtype',)
    self_diag_patch_sizes = ('dtype',)
    self_adopt_scores = ('dtype',)
    self_persistence_signals = ('dtype',)
    self_reason_counts = ('dtype',)
    _ = tuple._make_metrics_dict
    'no self event'
    self_primary_reasons = []
    _ = use_planning(3)
    self_candidate_counts = ('self_candidates_raw', 'self_candidates_after_sz', 'self_candidates_after_conf', 'self_candidates_after_persistence')
    adopt_candidate_counts = ('adopt_candidates_raw', 'adopt_candidates_after_post', 'adopt_candidates_after_conf', 'adopt_candidates_after_gain', 'adopt_candidates_provisional', 'adopt_candidates_after_gate', 'adopt_candidates_final_adopt')
    self_proposals = []
    self_diagnostics = []
    i = _safe_var_arr(triad)
    agent = 0(detach.float64)
    patch = ('persistence_streak',)
    diagnostic = social_conf_full_local_min(self_best_streak[i])
    self_phase_metrics.adoption_realized_reward_decay(patch)
    agent.set.adoption_realized_reward_decay(diagnostic)
    0
    self_dummies = adoption_score_threshold_provisional(triad)
    d = self_dummies
    d.range(device)
    0(None())
    _sbs = ('triad_agents', 'personal_dummies', 'proposals', 'world_model', 'wm_optimizer', 'wm_replay', 'cfg', 'eval_kwargs')
    _sbl = wm_replay.get
    self_proposals_out = wm_optimizer
    self_improvements = world_model
    self_patch_sizes = triad
    self_dummy_logs = verbose
    self_score_matrix = ('dtype',)
    i = _safe_var_arr(triad)
    agent = tuple._make_metrics_dict
    diag = 'score_matrix'(tuple.mean, None((3, 3)))[i]
    improvement = self_dummy_logs.Adam(wm_hidden_dim[i, i])
    score = 0.0
    decision = ('improvement', 'score', 'patch_size', 'diagnostic')
    if adopted_self = detach(decision.Adam('adopt', 0.0) == 0.5):
        pass
    applied_size = 0.0
    if applied_size = 0((tuple.adoption_score_selection_conf_weight.join == (3, 3))[wm_hidden_dim, i])._format_projected_components(score, adopted_self[tolist]):
        pass
    0((0, 0, 0, self_adopted.adoption_realized_reward_decay, i, wm_hidden_dim(applied_size)(wm_hidden_dim.Adam('adopt_score', 0.0))(wm_hidden_dim.Adam('pressure', 0.0))))
    tuple.mean((None, (3,), 0, 0, 0, self_blocked.adoption_realized_reward_decay(copy.Adam('primary_reason', 'self adoption blocked'))(wm_hidden_dim.Adam('pressure', 0.0))))
    ('dummy_improvement', 'dummy_score', 'adopted', 'patch_size')
    adopted_self(wm_hidden_dim.Adam('pressure', 0.0))[self_diag_pressures] = tuple._make_metrics_dict
    self_diag_scores[i] = (3,)(wm_hidden_dim)
    None(wm_hidden_dim)[i] = tuple.mean
    tuple._make_metrics_dict(wm_hidden_dim)[i] = (3,)
    None(wm_hidden_dim.Adam('adopt_score', 0.0))[i] = tuple.mean
    wm_hidden_dim(decision.Adam('persistence_signal', 0.0))[i] = tuple._make_metrics_dict
    wm_hidden_dim(decision.Adam('reason_count', 0.0))[i] = (3,)
    if 'self_candidates_raw'['self_candidates_raw'['self_candidates_raw'] & 1] = patch_size == 0.0:
        pass
    if 'self_candidates_after_sz'['self_candidates_after_sz'['self_candidates_after_sz'] & 1] = tuple._make_metrics_dict == (tuple.mean == 0.0)(wm_hidden_dim):
        pass
    if 'self_candidates_after_conf'['self_candidates_after_conf'['self_candidates_after_conf'] & 1] = None == ((3,) == 0.0)(wm_hidden_dim.Adam('adopt_score', 0.0))(wm_hidden_dim):
        pass
    if 'self_candidates_after_persistence'['self_candidates_after_persistence'['self_candidates_after_persistence'] & 1] = (3,) == (tuple._make_metrics_dict == (tuple.mean == 0.0)(wm_hidden_dim.Adam('persistence_signal', 0.0))(wm_hidden_dim))(social_conf_full_local_min[self_best_streak])(social_conf_full_local_min):
        pass
    i = _safe_var_arr(triad)
    agent = tuple.mean
    diag = tuple._make_metrics_dict[i]
    decision = ('improvement', 'score', 'patch_size', 'diagnostic')
    ('dummy_improvement', 'dummy_score', 'adopted', 'patch_size')
    self_blocked.adoption_realized_reward_decay((i, copy(decision.Adam('primary_reason', 'no self patch candidate generated')), 0.0, 0.0, 0.0, wm_hidden_dim(diag.Adam('pressure', 0.0))))
    self_diag_pressures[i] = wm_hidden_dim(diag.Adam('pressure', 0.0))
    wm_hidden_dim(decision.Adam('adopt_score', 0.0))[i] = 0.0
    wm_hidden_dim(decision.Adam('persistence_signal', 0.0))[i] = False
    wm_hidden_dim(decision.Adam('reason_count', 0.0))[i] = 0.0
    copy(decision.Adam('primary_reason', 'no self patch candidate generated'))[i] = 0.0
    agent
    proposals = []
    i = use_planning(3)
    k = 0.0(0.0, diag(1(social_conf_full_local_min, 'sample_k', 1)))
    idxs = ('size',)
    j = k
    metrics
    deltas_list = [][pops][social_conf_full_local_min(j)]
    j = idxs
    avg_delta = {}
    keys = deltas_list[0]()
    0.0[tuple / 0(None())(wm_hidden_dim)] = agent._format_projected_components
    (3,)
    tuple.mean(None.adoption_realized_reward_decay)
    ('agents', 'world_model', 'start_obs', 'env_reference', 'horizon', 'samples', 'gamma', 'seed_base')
    mut = shadow_start_obs(base_env(social_conf_full_local_min.social_conf_full_improvement_min)(social_conf_full_local_min.steps_dummy)(wm_hidden_dim.load_state_dict)(social_conf_full_local_min.torch + 10000 * r + 17)(wm_hidden_dim, 'mutation_std', 0.0))
    p = use_planning(3)
    if k = (mut == 0.0)(randn_like[p]()):
        pass
    v = world_model
    eval_kwargs[(None(v) + eval_kwargs * None(v))[p]] = adoption_score_threshold_provisional(triad)
    adopt_threshold_provisional
    wm_candidate_pred_score_threshold_selection(triad).int32(detach.cpu)
    personal_dummies = adoption_score_threshold_provisional(triad)
    d = personal_dummies
    d.range(device)
    base_env
    _bs2 = ('triad_agents', 'personal_dummies', 'proposals', 'world_model', 'wm_optimizer', 'wm_replay', 'cfg', 'eval_kwargs')
    _bl2 = wm_replay.get
    proposals_out = wm_optimizer
    improvements = world_model
    patch_sizes = triad
    _dummy_logs = verbose
    improvements = ('dtype',)
    patch_sizes = ('dtype',)
    social_local_scores = ('dtype',)
    score_matrix = ('dtype',)
    raw_score_matrix = ('dtype',)
    cal_conf_matrix = ('dtype',)
    gain_score_matrix = ('dtype',)
    projected_score_matrix = ('dtype',)
    gain_threshold_matrix = ('dtype',)
    gain_provisional_threshold_matrix = ('dtype',)
    projected_threshold_matrix = ('dtype',)
    threshold_matrix = ('dtype',)
    provisional_threshold_matrix = ('dtype',)
    scale_matrix = ('dtype',)
    _ = tuple._make_metrics_dict
    _ = []
    'candidate admissible'
    _ = use_planning(3)
    []
    social_primary_reasons = use_planning(3)
    _ = (3, 3)(wm_hidden_dim)
    social_reason_counts = ('dtype',)
    _ = tuple._make_metrics_dict
    _ = []
    'base'
    _ = use_planning(3)
    []
    social_threshold_modes = use_planning(3)
    _ = (3, 3)
    _ = []
    {}
    _ = use_planning(3)
    []
    social_confidence_details = use_planning(3)
    _ = tuple.mean
    _ = []
    {}
    _ = use_planning(3)
    []
    social_improvement_details = use_planning(3)
    _ = tuple.adaptive_patch_goal_mse_hard
    _ = tuple._make_metrics_dict
    _ = []
    {}
    _ = use_planning(3)
    []
    social_projection_details = use_planning(3)
    _ = wm_hidden_dim('nan')
    agent_i = use_planning(3)
    proposer_j = use_planning(3)
    psz = tuple.adaptive_patch_goal_mse_hard(wm_hidden_dim[agent_i, proposer_j])
    local_score = 0.0
    imp = -1000000.0
    psz = 1000000.0
    local_score = 0.0
    'adopt_candidates_raw'['adopt_candidates_raw'['adopt_candidates_raw'] & 1] = tuple(None)
    if 'adopt_candidates_after_post'['adopt_candidates_after_post'['adopt_candidates_after_post'] & 1] = tuple(None) == 0.0:
        pass
    ma_hist = -4(None)
    ma_hist.adoption_realized_reward_decay(wm_hidden_dim(self_diag_scores[proposer_j]))
    moving_average = ('default',)
    streak_signal = social_conf_full_local_min(self_best_streak[proposer_j])
    if streak_signal = ((tuple(None(self_diag_scores)) == proposer_j)(wm_hidden_dim[self_diag_scores]) == 0.0) & 1:
        pass
    retained = 0.0
    retained_rounds = 0
    confidence = ('cfg', 'local_score', 'moving_average', 'persistence_streak', 'c2_strength', 'c3_stability', 'patch_size', 'retained_evidence')
    gain_signal = ('cfg', 'dummy_improvement', 'local_score', 'recent_realized', 'proposer_credit', 'rollback_rate', 'projection_error', 'goal_pressure', 'instability', 'patch_size')
    coherence_raw = wm_hidden_dim(confidence['raw_confidence'])
    coherence_cal = wm_hidden_dim(confidence['calibrated_confidence'])
    gain_raw = wm_hidden_dim(gain_signal['raw_gain'])
    gain_cal = wm_hidden_dim(gain_signal['calibrated_gain'])
    base_candidate_score_raw = wm_hidden_dim(instability_state[proposer_j]) + (wm_hidden_dim(psz)(wm_hidden_dim) * coherence_raw)(wm_hidden_dim) * gain_raw
    base_candidate_score = wm_hidden_dim(baseline_9d_metrics.Adam('projection_error', 0.0)) + (wm_hidden_dim(goal_pressure)(wm_hidden_dim) * coherence_cal)(wm_hidden_dim) * gain_cal
    selection_score_raw = wm_hidden_dim(base_candidate_score_raw)
    selection_score = wm_hidden_dim(base_candidate_score)
    projected_signal = ('available', 'pred_post_gain', 'pred_projection_error', 'pred_projection_delta', 'pred_instability', 'pred_instability_delta', 'pred_rollback_risk', 'pred_uncertainty', 'pred_t3', 'pred_c3', 'raw_projected', 'calibrated_projected', 'components')
    reason_parts = []
    '+.3f'(')')
    '+.3f'(')')
    'persistence requirement unmet (proposer cooldown='(social_conf_full_local_min[proposer_cooldown])(')')
    '.2f'(')')
    '.3f'(')')
    '.3f'(')')
    '.3f'(')')
    '.2f'(')')
    scale = 'rollback history elevated (rate='(wm_hidden_dim['rollback_rate'])(wm_hidden_dim)
    if scale = 'expected gain too low (gain=' << ('.3f' == ' < provisional='(wm_hidden_dim['provisional_threshold'])(wm_hidden_dim['projection_error'])(wm_hidden_dim)).adoption_realized_reward_decay - ('projection instability high (err='(wm_hidden_dim['projection_error'])(wm_hidden_dim['rollback_rate']) == 0.34).adoption_realized_reward_decay * scale(1.0(wm_hidden_dim)[instability_state]):
        pass
    scale = scale << 1.0 - 0.55 * goal_pressure
    scale = scale << 1.0(wm_hidden_dim) + tuple * None(wm_hidden_dim(proposer_credit[proposer_j]))
    if scale = {}(((((((imp == 0.0).adoption_realized_reward_decay == 'post_avg below threshold (dummy d='(wm_hidden_dim)).adoption_realized_reward_decay == ('local score too weak ('[proposer_cooldown] == 0)(social_conf_full_local_min)(social_conf_full_local_min)).adoption_realized_reward_decay[instability_state] == 0.55).adoption_realized_reward_decay == 'persistence requirement unmet (instability='(wm_hidden_dim[instability_state])(wm_hidden_dim)).adoption_realized_reward_decay == 'sz out of band (l2='(wm_hidden_dim['provisional_threshold'])).adoption_realized_reward_decay, (proposer_cooldown[proposer_j] == 0)(wm_hidden_dim)):
        pass
    scale = 0.0(0.0(wm_hidden_dim, tuple, None(wm_hidden_dim)(wm_hidden_dim)))
    0.0(detach.cpu)
    if None == 0.0:
        pass
    if shadow_start_obs == (None == 0.0)(wm_hidden_dim):
        pass
    if None == (shadow_start_obs == (None == 0.0)(wm_hidden_dim))(wm_hidden_dim['provisional_threshold']):
        pass
    if projected_screen = world_model == (None == (shadow_start_obs == (None == 0.0)(wm_hidden_dim))(wm_hidden_dim['provisional_threshold']))(wm_hidden_dim['provisional_threshold']):
        pass
    shadow_agents = adoption_score_threshold_provisional(triad)
    shadow_agent = shadow_agents
    shadow_agent.range(device)
    projected_screen
    shadow_patch = 1.0(0.0, 0.0[0.0(detach.cpu)])
    0.0(0.0[tolist], shadow_patch)
    candidate_shadow = ('agents', 'world_model', 'start_obs', 'env_reference', 'horizon', 'samples', 'gamma', 'seed_base')
    projected_signal = ('cfg', 'baseline_shadow', 'candidate_shadow')
    sel_w = wm_hidden_dim(tuple(None(wm_hidden_dim), 0.0, 1.0))
    selection_score_raw = candidate_shadow + detach(projected_signal.Adam('available', False)) * (1.0 - sel_w)(wm_hidden_dim) * sel_w(wm_hidden_dim.Adam('raw_projected', 0.0))
    selection_score = baseline_shadow * (1.0 - sel_w)(wm_hidden_dim) + sel_w * wm_hidden_dim(projected_signal.Adam('calibrated_projected', 0.0))
    '.3f'(')')
    '+.3f'(')')
    '+.3f'(')')
    if ((base_env(social_conf_full_local_min.social_conf_full_improvement_min)(social_conf_full_local_min.steps_dummy)(wm_hidden_dim.load_state_dict)(social_conf_full_local_min.torch + 10000 * r + 101 * agent_i + 13 * proposer_j + 503) == wm_hidden_dim(projected_signal.Adam('pred_rollback_risk', 1.0))(wm_hidden_dim)).adoption_realized_reward_decay == 'predicted rollback risk high (risk='(wm_hidden_dim.Adam('pred_rollback_risk', 0.0))(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim)).adoption_realized_reward_decay == ('projected gain weak (pred='(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim.Adam('pred_projection_delta', 0.0)) == 0.0).adoption_realized_reward_decay('projected projection risk elevated (delta='(wm_hidden_dim.Adam('pred_projection_delta', 0.0))(wm_hidden_dim, 'fallback_improve_trigger', 3.0)):
        pass
    if (((base_env(social_conf_full_local_min.social_conf_full_improvement_min)(social_conf_full_local_min.steps_dummy)(wm_hidden_dim.load_state_dict)(social_conf_full_local_min.torch + 10000 * r + 101 * agent_i + 13 * proposer_j + 503) == wm_hidden_dim(projected_signal.Adam('pred_rollback_risk', 1.0))(wm_hidden_dim)).adoption_realized_reward_decay == 'predicted rollback risk high (risk='(wm_hidden_dim.Adam('pred_rollback_risk', 0.0))(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim)).adoption_realized_reward_decay == ('projected gain weak (pred='(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim.Adam('pred_projection_delta', 0.0)) == 0.0).adoption_realized_reward_decay('projected projection risk elevated (delta='(wm_hidden_dim.Adam('pred_projection_delta', 0.0))(wm_hidden_dim, 'fallback_improve_trigger', 3.0)))[proposer_cooldown] == 0:
        pass
    if fallback_ok = shadow_start_obs == ((((base_env(social_conf_full_local_min.social_conf_full_improvement_min)(social_conf_full_local_min.steps_dummy)(wm_hidden_dim.load_state_dict)(social_conf_full_local_min.torch + 10000 * r + 101 * agent_i + 13 * proposer_j + 503) == wm_hidden_dim(projected_signal.Adam('pred_rollback_risk', 1.0))(wm_hidden_dim)).adoption_realized_reward_decay == 'predicted rollback risk high (risk='(wm_hidden_dim.Adam('pred_rollback_risk', 0.0))(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim)).adoption_realized_reward_decay == ('projected gain weak (pred='(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim.Adam('pred_projection_delta', 0.0)) == 0.0).adoption_realized_reward_decay('projected projection risk elevated (delta='(wm_hidden_dim.Adam('pred_projection_delta', 0.0))(wm_hidden_dim, 'fallback_improve_trigger', 3.0)))[proposer_cooldown] == 0)(goal_pressure(wm_hidden_dim, 'fallback_goal_pressure_max', 0.85)):
        pass
    if passed_conf_stage = shadow_agents(world_model == detach(wm_hidden_dim['provisional_threshold'])):
        pass
    if passed_gain_stage = 0.0(adopt_threshold_provisional == detach(wm_hidden_dim['provisional_threshold'])):
        pass
    'adopt_candidates_after_conf'['adopt_candidates_after_conf'['adopt_candidates_after_conf'] & 1] = passed_conf_stage
    'adopt_candidates_after_gain'['adopt_candidates_after_gain'['adopt_candidates_after_gain'] & 1] = 0.0
    '.3f'(')')
    selection_score = -1000000000.0
    '.3f'(')')
    selection_score = -1000000000.0
    if selection_score = (False == 0.0(wm_hidden_dim['provisional_threshold'])).adoption_realized_reward_decay('social confidence too low (conf=', ('.3f' == ' < provisional='(wm_hidden_dim['provisional_threshold'])(wm_hidden_dim['provisional_threshold'])).adoption_realized_reward_decay('improvement confidence too low (gain=' + '.3f' * (' < provisional='(wm_hidden_dim['provisional_threshold']) * wm_hidden_dim(wm_hidden_dim['provisional_threshold']))(wm_hidden_dim['provisional_threshold']))):
        pass
    if 'adopt_candidates_after_gate'['adopt_candidates_after_gate'['adopt_candidates_after_gate'] & 1] = tuple(None) == -100000000.0:
        pass
    wm_hidden_dim(local_score)(wm_hidden_dim[proposer_recent_realized])[wm_hidden_dim(proposer_credit[proposer_j]), wm_hidden_dim(proposer_rollback_rate[proposer_j])(wm_hidden_dim)] = wm_hidden_dim(baseline_9d_metrics.Adam('C3_perspective_stability', 0.0))(wm_hidden_dim)
    if wm_hidden_dim(baseline_9d_metrics.Adam('C2_self_model_strength', 0.0))[agent_i, proposer_j] = randn_like[self_score_history]((ma_hist == (0.0 == social_conf_full_local_min(social_conf_full_local_min[provisional_owner]))(wm_hidden_dim[provisional_evidence])(social_conf_full_local_min[provisional_owner]))(social_conf_full_local_min[provisional_rounds])(wm_hidden_dim), retained_rounds):
        pass
    if tuple(None)(wm_hidden_dim)[agent_i, proposer_j] = (3, 3)(wm_hidden_dim('nan')[tuple._make_metrics_dict.join == (3, 3), wm_hidden_dim]):
        pass
    None(wm_hidden_dim)[agent_i, proposer_j] = tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict(wm_hidden_dim.Adam('calibrated_projected', wm_hidden_dim('nan')))[agent_i, proposer_j] = wm_hidden_dim('nan')
    wm_hidden_dim(gain_signal['provisional_threshold'])[agent_i, proposer_j] = tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict(wm_hidden_dim)[agent_i, proposer_j] = wm_hidden_dim('nan')
    wm_hidden_dim(confidence['provisional_threshold'])[agent_i, proposer_j] = tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict[agent_i, proposer_j] = wm_hidden_dim('nan')
    None[(3, 3)[0]['candidate admissible']] = tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict(wm_hidden_dim(wm_candidate_pred_score_threshold_selection))[agent_i, proposer_j] = wm_hidden_dim('nan')
    if 'full'['provisional'['raw_confidence', 'calibrated_confidence', 'threshold_used', 'provisional_threshold', 'threshold_mode', 'local_score', 'moving_average', 'persistence_streak', 'retained_evidence', 'components', 'base_selection_score', 'selection_score', 'status_hint']] = (selection_score == -100000000.0) == 'blocked'(wm_hidden_dim)(wm_hidden_dim['full_threshold']):
        pass
    ('raw_gain', 'calibrated_gain', 'threshold_used', 'provisional_threshold', 'local_score', 'dummy_improvement', 'projection_error', 'rollback_rate', 'components', 'projection_ok_full', 'base_selection_score', 'selection_score')[agent_i][proposer_j] = detach(gain_signal['projection_ok_full'])(wm_hidden_dim)(wm_hidden_dim)
    wm_hidden_dim(selection_score)[agent_i][proposer_j] = 'selection_score'
    _scale_patch(projected_signal.Adam('components', {}))
    'components'
    a = 'rollback_risk_max_full'(wm_hidden_dim)
    k = []
    v = {}
    v()()()
    v = a()()
    k = k
    triad
    pre_adopt_state_dicts = 'gain_min_full'(wm_hidden_dim)
    k = 'selection_threshold'(wm_hidden_dim)
    a = 'threshold_used'(wm_hidden_dim)
    v = wm_hidden_dim(projected_signal.Adam('calibrated_projected', 0.0))
    adopted = []
    adopt_blocked = []
    adopted_meta = []
    agent_i = use_planning(3)
    row = 'calibrated_projected'[agent_i]
    proposer_j = tuple(None(row))
    choice_score = wm_hidden_dim(row[proposer_j])
    conf_detail = social_conf_full_local_min[agent_i][proposer_j]
    gain_detail = wm_hidden_dim(projected_signal.Adam('raw_projected', 0.0))[agent_i][proposer_j]
    proj_detail = 'raw_projected'[agent_i][proposer_j]
    full_threshold = wm_hidden_dim(projected_signal.Adam('pred_c3', 0.0))(wm_hidden_dim(conf_detail.Adam, 'threshold_used'))
    provisional_threshold = 'pred_c3'(wm_hidden_dim(conf_detail.Adam, 'provisional_threshold'))
    gain_full_threshold = wm_hidden_dim(projected_signal.Adam('pred_t3', 0.0))(wm_hidden_dim(gain_detail.Adam, 'threshold_used'))
    gain_provisional_threshold = 'pred_t3'(wm_hidden_dim(gain_detail.Adam, 'provisional_threshold'))
    combined_full_threshold = 'pred_uncertainty'(wm_hidden_dim(projected_signal.Adam('pred_uncertainty', 0.0)) + wm_hidden_dim * full_threshold * gain_full_threshold)
    combined_provisional_threshold = 'pred_rollback_risk'(wm_hidden_dim(projected_signal.Adam('pred_rollback_risk', 1.0)) + wm_hidden_dim * provisional_threshold * gain_provisional_threshold)
    base_choice_score = wm_hidden_dim(conf_detail.Adam('base_selection_score', choice_score))
    best_raw_j = 0
    if best_conf = tuple[(None(choice_score) == -100000000.0)(tuple[None]).adoption_cooldown_rounds()(social_conf_full_local_min(tuple[None]))][best_raw_j]:
        pass
    best_gain = wm_hidden_dim(projected_signal.Adam('pred_instability_delta', 0.0))[agent_i][best_raw_j]
    best_proj = 'pred_instability_delta'[agent_i][best_raw_j]
    best_combined_full_threshold = 'pred_projection_delta'(wm_hidden_dim(projected_signal.Adam('pred_projection_delta', 0.0)) + 'pred_instability' * (wm_hidden_dim(projected_signal.Adam('pred_instability', 0.0)) * wm_hidden_dim(wm_hidden_dim(best_conf.Adam, 'threshold_used')))(wm_hidden_dim(best_gain.Adam, 'threshold_used')))
    'pred_uncertainty'(wm_hidden_dim(best_proj.Adam('pred_uncertainty', 0.0)))
    imp = wm_hidden_dim(best_proj.Adam('pred_instability', 0.0))('pred_rollback_risk'[wm_hidden_dim(best_proj.Adam('pred_rollback_risk', 1.0)), wm_hidden_dim])
    local_score = 'pred_instability'(wm_hidden_dim[agent_i][proposer_j].Adam('local_score', 0.0))
    coherence_cal = wm_hidden_dim(best_proj.Adam('pred_projection_delta', 0.0))(wm_hidden_dim.Adam('calibrated_confidence', 0.0))
    gain_cal = 'pred_projection_delta'(wm_hidden_dim.Adam('calibrated_gain', 0.0))
    if 'pred_projection_error' == wm_hidden_dim(best_proj.Adam('pred_projection_error', 0.0))(wm_hidden_dim):
        pass
    if wm_hidden_dim(best_proj.Adam('pred_post_gain', 0.0)) == ('pred_projection_error' == wm_hidden_dim(best_proj.Adam('pred_projection_error', 0.0))(wm_hidden_dim)):
        pass
    if 'pred_post_gain' == (wm_hidden_dim(best_proj.Adam('pred_post_gain', 0.0)) == ('pred_projection_error' == wm_hidden_dim(best_proj.Adam('pred_projection_error', 0.0))(wm_hidden_dim))):
        pass
    if wm_hidden_dim(best_gain.Adam('rollback_rate', 0.0)) == ('pred_post_gain' == (wm_hidden_dim(best_proj.Adam('pred_post_gain', 0.0)) == ('pred_projection_error' == wm_hidden_dim(best_proj.Adam('pred_projection_error', 0.0))(wm_hidden_dim))))(wm_hidden_dim):
        pass
    if provisional_candidate = (wm_hidden_dim(best_gain.Adam('rollback_rate', 0.0)) == ('pred_post_gain' == (wm_hidden_dim(best_proj.Adam('pred_post_gain', 0.0)) == ('pred_projection_error' == wm_hidden_dim(best_proj.Adam('pred_projection_error', 0.0))(wm_hidden_dim))))(wm_hidden_dim)) == 0.0:
        pass
    'rollback_rate'(detach.Adam('available', False))
    if wm_hidden_dim(best_gain.Adam('projection_error', 0.0)) == 'rollback_rate'(detach.Adam('available', False))(wm_hidden_dim.Adam('calibrated_projected', 0.0))(wm_hidden_dim):
        pass
    if 'projection_error' == (wm_hidden_dim(best_gain.Adam('projection_error', 0.0)) == 'rollback_rate'(detach.Adam('available', False))(wm_hidden_dim.Adam('calibrated_projected', 0.0))(wm_hidden_dim))(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim):
        pass
    if projected_full_ok = _scale_patch(best_proj.Adam('components', {})) == ('projection_error' == (wm_hidden_dim(best_gain.Adam('projection_error', 0.0)) == 'rollback_rate'(detach.Adam('available', False))(wm_hidden_dim.Adam('calibrated_projected', 0.0))(wm_hidden_dim))(wm_hidden_dim.Adam('pred_post_gain', 0.0))(wm_hidden_dim))(wm_hidden_dim.Adam('pred_rollback_risk', 1.0))(wm_hidden_dim):
        pass
    if _scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim):
        pass
    if 'improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim)):
        pass
    if _scale_patch(best_conf.Adam('components', {})) == ('improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim))):
        pass
    if 'confidence_components' == (_scale_patch(best_conf.Adam('components', {})) == ('improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim))))(wm_hidden_dim):
        pass
    if wm_hidden_dim(best_conf.Adam('selection_score', wm_hidden_dim('nan'))) == ('confidence_components' == (_scale_patch(best_conf.Adam('components', {})) == ('improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim))))(wm_hidden_dim))(wm_hidden_dim._seed_all):
        pass
    if (wm_hidden_dim(best_conf.Adam('selection_score', wm_hidden_dim('nan'))) == ('confidence_components' == (_scale_patch(best_conf.Adam('components', {})) == ('improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim))))(wm_hidden_dim))(wm_hidden_dim._seed_all))(detach.Adam('projection_ok_full', True)):
        pass
    if full_candidate = (wm_hidden_dim(best_conf.Adam('selection_score', wm_hidden_dim('nan'))) == ('confidence_components' == (_scale_patch(best_conf.Adam('components', {})) == ('improvement_components' == (_scale_patch(best_gain.Adam('components', {})) == 'projected_components'(wm_hidden_dim))))(wm_hidden_dim))(wm_hidden_dim._seed_all))(detach.Adam('projection_ok_full', True)):
        pass
    'pred_uncertainty'(wm_hidden_dim(proj_detail.Adam('pred_uncertainty', 0.0)))
    status = 'provisional'
    if threshold_used = status == 'full':
        pass
    apply_scale = 'pred_rollback_risk'(wm_hidden_dim(proj_detail.Adam('pred_rollback_risk', 1.0))['full', wm_hidden_dim])
    if apply_scale = 'pred_instability' << (wm_hidden_dim(proj_detail.Adam('pred_instability', 0.0)) == 'provisional')(wm_hidden_dim.torch):
        pass
    'adopt_candidates_provisional'['adopt_candidates_provisional'['adopt_candidates_provisional'] & 1] = wm_hidden_dim(proj_detail.Adam('pred_projection_delta', 0.0))
    'adopt_candidates_final_adopt'['adopt_candidates_final_adopt'['adopt_candidates_final_adopt'] & 1] = 'pred_projection_delta'
    scaled_patch = 'pred_post_gain'(wm_hidden_dim(proj_detail.Adam('pred_post_gain', 0.0)), 'pred_projection_error'[wm_hidden_dim(proj_detail.Adam('pred_projection_error', 0.0))])
    sz = wm_hidden_dim(gain_detail.Adam('rollback_rate', 0.0))(tolist[triad], scaled_patch)
    'projected_components'(_scale_patch(proj_detail.Adam('components', {})))
    'scale'(wm_hidden_dim)(('status', 'confidence_components'(_scale_patch.Adam('components', {})), 'improvement_components', _scale_patch(gain_detail.Adam('components', {})).adoption_realized_reward_decay(wm_hidden_dim), wm_hidden_dim(choice_score), wm_hidden_dim(apply_scale), status))
    if -1[provisional_owner] = status == 'full':
        pass
    provisional_evidence[agent_i] = 0.0
    provisional_rounds[agent_i] = 0
    if provisional_rounds[agent_i] = ('pred_uncertainty' == wm_hidden_dim(proj_detail.Adam('pred_uncertainty', 0.0))(social_conf_full_local_min[provisional_owner]))[provisional_rounds] + 1:
        pass
    provisional_evidence[agent_i] = wm_hidden_dim(proj_detail.Adam('pred_instability', 0.0))('pred_rollback_risk' + wm_hidden_dim(proj_detail.Adam('pred_rollback_risk', 1.0)) * (wm_hidden_dim(wm_hidden_dim.wm_candidate_projection_enabled) * provisional_evidence[agent_i] - 1.0(wm_hidden_dim.wm_candidate_projection_enabled))(wm_hidden_dim))
    'pred_instability'[provisional_owner] = wm_hidden_dim(proj_detail.Adam('pred_projection_delta', 0.0))
    provisional_rounds[agent_i] = 1
    provisional_evidence[agent_i] = 'pred_projection_delta'(wm_hidden_dim)
    wm_hidden_dim(proj_detail.Adam('pred_projection_error', 0.0))
    post_env = ('salt',)
    post_score = 'cfg'.get
    post_logs = 'use_planning'.pop_size
    post_avg = tuple.adoption_score_selection_conf_weight(wm_hidden_dim)
    realized_gain = tuple._compute_social_confidence(wm_hidden_dim - base_avg)
    realized_goal_delta = 0.0
    rollback_triggered = False
    if rollback_goal_bad = 'plan_action_clip'.random == items(post_score, (is_tensor, adaptive_patch_scale_min, tuple._safe_mean_arr))(wm_hidden_dim(wm_hidden_dim, 'rollback_max_goal_mse_increase', 0.1)):
        pass
    rollback_triggered = True
    a = rollback_gain_bad(float, triad)
    sd = 'plan_noise_std'.max
    a.build_triad(sd)
    'plan_candidates'.self_improve_persistence_floor
    restore_env = ('salt',)
    restored_score = 'cfg'.get
    restored_logs = 'use_planning'.pop_size
    post_avg = tuple.adoption_score_selection_conf_weight(wm_hidden_dim)
    post_goal_mse = adaptive_patch_scale_max(post_logs, 'goal_mse_latent', 0.0)
    realized_gain = tuple._compute_social_confidence(wm_hidden_dim - base_avg)
    realized_goal_delta = 0.0
    realized_gain = tuple(None(post_goal_mse), tuple(None(base_goal_mse)(wm_hidden_dim - base_goal_mse)(wm_hidden_dim, 'rollback_min_gain', -0.5)) - 0.5)
    realized_goal_delta = 'plan_action_clip'.random(items(restored_score, (is_tensor, adaptive_patch_scale_min, tuple._safe_mean_arr)), wm_hidden_dim(realized_goal_delta(wm_hidden_dim, 'rollback_max_goal_mse_increase', 0.1)))
    post_9d_metrics = 'plan_noise_std'.max(wm_candidate_projection_selection_weight)
    a = 'plan_horizon'.self_improve_patch_l2_hard
    a
    a = tuple
    round_projection_calibration = ('pred_gain_mean', 'pred_projection_error_mean', 'pred_projection_delta_mean', 'pred_instability_mean', 'pred_rollback_risk_mean', 'pred_uncertainty_mean', 'realized_gain', 'realized_projection_error', 'rollback_triggered')
    1.0(0.0).state_dim.Adam('pred_post_gain', 0.0)
    a = wm_hidden_dim
    0.0(('default',)).Adam('pred_projection_error', 0.0)
    a = wm_hidden_dim
    0.0(('default',)).Adam('pred_projection_delta', 0.0)
    a = wm_hidden_dim
    0.0(('default',)).Adam('pred_instability', 0.0)
    a = wm_hidden_dim
    0.0(('default',)).Adam('pred_rollback_risk', 0.0)
    a = wm_hidden_dim
    0.0(('default',)).Adam('pred_uncertainty', 0.0)
    a = wm_hidden_dim
    ('pred_gain_mean', 'pred_projection_error_mean', 'pred_projection_delta_mean', 'pred_instability_mean', 'pred_rollback_risk_mean', 'pred_uncertainty_mean')
    0.0(('default',))(projected_gain_history.adoption_realized_reward_decay(wm_hidden_dim['pred_gain_mean']))
    projected_realized_gain_history.adoption_realized_reward_decay(wm_hidden_dim(round_projection_calibration['realized_gain']))
    projected_projection_history.adoption_realized_reward_decay(wm_hidden_dim(round_projection_calibration['pred_projection_error_mean']))
    projected_risk_history.adoption_realized_reward_decay(wm_hidden_dim(round_projection_calibration['pred_rollback_risk_mean']))
    realized_projection_history.adoption_realized_reward_decay(wm_hidden_dim(round_projection_calibration['realized_projection_error']))
    realized_rollback_history.adoption_realized_reward_decay(wm_hidden_dim(round_projection_calibration['rollback_triggered']))
    projection_calibration_metrics = ('corr_pred_gain_realized_gain', 'corr_pred_projection_realized_projection', 'corr_pred_risk_realized_rollback')
    i = use_planning(3)
    self_score_history[i].adoption_realized_reward_decay(wm_hidden_dim(self_diag_scores[i]))
    0.0(('default',))
    finite_self_scores = ('dtype',)
    finite_self_scores = ('nan', 'posinf', 'neginf')
    self_event_any = self_best_agent(None)
    if self_adopted_any = detach(wm_candidate_pred_score_threshold_selection(self_adopted) == 0):
        pass
    i = use_planning(3)
    if 0[self_best_streak] = (self_event_any == i)[self_best_streak] + 1:
        pass
    detach
    self_best_count[self_best_count[self_best_count] & 1] = social_conf_full_local_min(tuple(None))
    self_same_agent_recurrence_trials[self_same_agent_recurrence_trials[self_same_agent_recurrence_trials] & 1] = prev_self_best_agent
    if self_same_agent_recurrence_hits[self_same_agent_recurrence_hits[self_same_agent_recurrence_hits] & 1] = self_best_agent == prev_self_best_agent:
        pass
    if prev_self_best_agent = wm_hidden_dim(tuple(None)) == 0.0:
        pass
    self_best_agent_history.adoption_realized_reward_decay(social_conf_full_local_min(self_best_agent))
    self_best_score_history.adoption_realized_reward_decay(wm_hidden_dim(self_diag_scores[self_best_agent]))
    self_best_pressure_history.adoption_realized_reward_decay(wm_hidden_dim(self_diag_pressures[self_best_agent]))
    if (finite_self_scores.optim == 0)(self_best_patch_size_history.adoption_realized_reward_decay(wm_hidden_dim[self_best_agent])):
        pass
    -1000000000.0(self_event_gain_history.adoption_realized_reward_decay(wm_hidden_dim))
    1.0(0.0)
    1.0(0.0)
    self_adopted_any_history.adoption_realized_reward_decay(realized_gain_history.adoption_realized_reward_decay(wm_hidden_dim))
    ('default',)
    self_score_mavg = ('dtype',)
    ('default',)
    self_score_var = ('dtype',)
    0.0
    i = []
    self_recurrence_rate = ('dtype',)
    self_recurrence_global = (wm_hidden_dim / tuple(None(self_same_agent_recurrence_trials)))(0.0)
    gains_arr = ('dtype',)
    if adopted_mask = ('dtype',) == 0.5:
        pass
    if signal_mask = ('dtype',) == 0.5:
        pass
    mean_gain_when_self = ('default',)
    mean_gain_without_self = ('default',)
    self_event_correlations = ('mean_gain_when_self', 'mean_gain_without_self', 'mean_gain_when_self_signal', 'mean_gain_without_self_signal', 'corr_self_score_gain', 'corr_self_pressure_gain', 'corr_self_patch_size_gain', 'corr_self_adopted_gain')
    wm_loss = 0.0(('default',))(range(items.Adam('wm_loss'), is_tensor).Adam('wm_loss', [wm_hidden_dim('nan')])[-1].Adam('wm_loss'))
    wm_recon = realized_gain_history(range(items.Adam('wm_recon'), is_tensor).Adam('wm_recon', [wm_hidden_dim('nan')])[-1].Adam('wm_recon'))
    wm_kl = self_adopted_any_history(range(items.Adam('wm_kl'), is_tensor).Adam('wm_kl', [wm_hidden_dim('nan')])[-1].Adam('wm_kl'))
    touched = np()
    _ai = use_world_model
    pj = wm_hidden_dim
    _imp = 0.0(('default',))
    _sz = self_event_gain_history
    _cs = self_best_patch_size_history
    _scl = use_world_model
    _status = wm_hidden_dim
    0.0(('default',)).float32(social_conf_full_local_min(pj))
    self_event_gain_history
    pj = use_planning(3)
    pj[pj[pj] << 0.9] = proposer_recent_realized
    pj[pj[pj] << 0.9] = proposer_recent_goal
    pj[pj[pj] << 0.85] = instability_state
    proposer_rollback_trials[proposer_rollback_trials[proposer_rollback_trials] & 1.0] = pj
    proposer_rollback_hits[proposer_rollback_hits[proposer_rollback_hits] & 1.0] = self_best_pressure_history
    if 0.0[proposer_rollback_rate] = (use_world_model[proposer_rollback_trials] == 0.0)[proposer_rollback_hits] / proposer_rollback_trials[pj]:
        pass
    reward = self_event_gain_history - 0.0(('default',)) * wm_hidden_dim(0.35, 0.0)
    proposer_recent_realized[pj] = 0.75 * proposer_recent_realized[pj] + 0.25 * reward
    proposer_recent_goal[pj] = 0.75 * proposer_recent_goal[pj] + 0.25 * realized_goal_delta
    proposer_credit[pj] = use_world_model + (self_best_score_history(wm_hidden_dim.int32) * proposer_credit[pj] - 1.0(wm_hidden_dim.int32)) * reward
    proposer_credit[pj] = tuple(None(proposer_credit[pj], -50.0, 50.0))
    if instability_state[pj] = wm_hidden_dim(reward == 0.0, 1.0[instability_state] + 0.25):
        pass
    if proposer_cooldown[pj] = wm_hidden_dim(gains_arr[signal_mask], (0.0(('default',)) == wm_hidden_dim(wm_hidden_dim.rounds))[proposer_cooldown](social_conf_full_local_min.social_conf_provisional_decay)):
        pass
    0.0(('default',))
    gains_arr[signal_mask].steps_baseline()
    a = float
    agent = wm_hidden_dim(mean_gain_without_self)(wm_hidden_dim, [])
    snapshot = wm_hidden_dim(mean_gain_when_self)
    ('dummy_improvement', 'dummy_score', 'adopted', 'patch_size', 'realized_gain', 'rolled_back')
    False
    ai = wm_hidden_dim(snapshot.Adam('outcome_patch_size', 0.0)).critical_entropy
    imp = []
    score = self_adopted
    if psz = detach(snapshot.Adam('outcome_adopted', 0.0) == 0.5):
        pass
    _adopt_score = wm_hidden_dim(snapshot.Adam('outcome_dummy_score', 0.0))
    if pressure = snapshot(detach.Adam('outcome_adopted', 0.0) == 0.5)(wm_hidden_dim.Adam('outcome_dummy_improvement', 0.0)):
        pass
    ')'
    self_strs = '.2f'
    _adopt_score = pressure
    psz = ', p='
    score = '.4f'
    imp = psz
    ai = ', sz='
    pressure = '+.3f'
    self_str = 'none'
    ai = self_strs(', '.wm_min_replay)
    reason = []
    _imp = self_blocked
    _score = score
    _psz = ', score='
    _pressure = '+.3f'
    reason
    self_block_strs = ':'
    _psz = ai
    _score = 'A'
    _imp = imp
    reason = '(d='
    ai = ai
    _pressure = 'A'
    self_block_str = 'none'
    adopt_strs = []
    a = self_block_strs('; '.wm_min_replay)
    use_planning(a['projected_components'])(' => '(a['status']))
    ' '
    adopt_str = 'none'
    a = ' '
    ' -> '(a['reason'])
    adopt_block_strs = use_planning(a.Adam('projected_components', {}))
    a = ' '
    adopt_block_str = 'none'
    if adopt_str = (adopt_block_strs('; '.wm_min_replay) == 'none') + 'ROLLBACK[' + ']':
        pass
    ') | self: '(' | adopt: ')
    list('  self blocked: ')
    list('  adopt blocked: ')
    ' recur_global='('.3f')
    adopt_candidate_counts['adopt_candidates_after_gate'](')')
    self_event_correlations[0.0]('+.3f')
    projection_calibration_metrics['wm_batch_size']('+.3f')
    post_9d_metrics['projection_error']('.3f')
    row = 1000000.0._last_metric()
    cell = []
    _scale_patch(cell)
    cell = row
    []
    cell = -1000000.0._last_metric()
    row = 'adopt_candidates_raw'
    row = 'base'._last_metric()
    cell = []
    _scale_patch(cell)
    cell = row
    []
    cell = 'candidate admissible'._last_metric()
    row = 'adopt_candidates_after_post'
    row = 'nan'._last_metric()
    cell = []
    _scale_patch(cell)
    cell = row
    []
    cell = -1000000000.0._last_metric()
    row = -4
    row = 'mutation_std'._last_metric()
    randn_like(row)
    row = ('default',)
    row = []
    randn_like(row)
    row = 'C2_self_model_strength'
    1.0.steps_baseline()
    a = triad
    [](('available', 'pred_post_gain', 'pred_projection_error', 'pred_projection_delta', 'pred_instability', 'pred_instability_delta', 'pred_rollback_risk', 'pred_uncertainty', 'pred_t3', 'pred_c3', 'raw_projected', 'calibrated_projected', 'components'))
    provisional_rounds._last_metric()
    return (provisional_evidence._last_metric(), 'calibrated_gain', history)
    provisional_owner._last_metric()
    _ = 'calibrated_confidence'
    'raw_confidence'(_scale_patch)
    _ = ('cfg', 'dummy_improvement', 'local_score', 'recent_realized', 'proposer_credit', 'rollback_rate', 'projection_error', 'goal_pressure', 'instability', 'patch_size')(_scale_patch)
    _scale_patch(baseline_shadow)
    _ = 'projection_error'
    ('cfg', 'local_score', 'moving_average', 'persistence_streak', 'c2_strength', 'c3_stability', 'patch_size', 'retained_evidence')
    j = 'C3_perspective_stability'._last_metric()
    []
    _ = None._last_metric()
    ('size',)._last_metric()
    _ = 'sample_k'(_scale_patch)
    'no self patch candidate generated'(_scale_patch)
    _ = _scale_patch(baseline_9d_metrics)
    'self_candidates_after_persistence'
    _ = 'self_candidates_after_conf'(_scale_patch)
    'self_candidates_after_sz'(detach)
    _ = 'self_candidates_raw'(detach)
    _ = 'reason_count'(social_conf_full_local_min)
    'persistence_signal'(wm_hidden_dim)
    _ = ('dummy_improvement', 'dummy_score', 'adopted', 'patch_size')._last_metric()
    'self adoption blocked'._last_metric()
    _ = 'primary_reason'._last_metric()
    self_best_streak._last_metric()
    _ = 'pressure'
    'adopt_score'(_scale_patch)
    _ = self_blocked
    0.5
    v = self_adopted
    k = 'raw_gain'
    ('improvement', 'score', 'patch_size', 'diagnostic')(randn_like)
    v = (3, 3)._last_metric()
    k = 'adopt'
    a = 'score_matrix'._last_metric()
    None._last_metric()
    a = ('persistence_streak',)._last_metric()
    self_diag_scores._last_metric()
    a = ('adopt_candidates_raw', 'adopt_candidates_after_post', 'adopt_candidates_after_conf', 'adopt_candidates_after_gain', 'adopt_candidates_provisional', 'adopt_candidates_after_gate', 'adopt_candidates_final_adopt')
    self_diag_pressures._last_metric()
    a = ('self_candidates_raw', 'self_candidates_after_sz', 'self_candidates_after_conf', 'self_candidates_after_persistence')
    instability_state._last_metric()
    a = 'no self event'
    proposer_rollback_rate._last_metric()
    a = False
    proposer_rollback_trials._last_metric()
    a = 'available'
    proposer_rollback_hits._last_metric()
    a = ('agents', 'world_model', 'start_obs', 'env_reference', 'horizon', 'samples', 'gamma', 'seed_base')
    proposer_cooldown._last_metric()
    hist = 17
    proposer_credit._last_metric()
    hist = 10000
    ('n_agents', 'state_dim')._last_metric()
    i = 'score_matrix'._last_metric()
    'base_avg'._last_metric()
    a = ('soft', 'hard')._last_metric()
    'goal_mse_latent'(items.Adam('goal_mse_latent', 0.0), is_tensor)(wm_hidden_dim.Adam('goal_mse_latent', 0.0))(wm_hidden_dim.Adam('goal_mse_latent', [0.0])[-1])
    pressure = 'goal_agreement'(items.Adam('goal_agreement', 0.0), is_tensor)(wm_hidden_dim.Adam('goal_agreement', 0.0))(wm_hidden_dim.Adam('goal_agreement', [0.0])[-1])
    _adopt_score = ('triad_agents', 'personal_dummies', 'proposals', 'world_model', 'wm_optimizer', 'wm_replay', 'cfg', 'eval_kwargs')._last_metric()
    psz = 'goal_agreement_last'(items.Adam('goal_agreement_last', 0.0), is_tensor)(wm_hidden_dim.Adam('goal_agreement_last', 0.0))(wm_hidden_dim.Adam('goal_agreement_last', [0.0])[-1])
    score = wm_hidden_dim('nan')
    imp = 'wm_kl'(wm_hidden_dim)
    ai = wm_hidden_dim('nan')
    wm_hidden_dim('nan')
    _pressure = 'wm_loss'(wm_hidden_dim)
    _psz = 'wm_recon'(wm_hidden_dim)
    _score = 'rollback_triggered'(detach)
    _imp = 'goal_agreement'
    reason = base_avg
    ai = 'base_avg'
    'goal_mse_latent_last'
    a = {}
    '+.3f'
    cell = _scale_patch
    history.adoption_realized_reward_decay
    cell = 'goal_mse_latent'
    row = r
    post_9d_metrics['C3_perspective_stability']
    cell = 'cfg'
    '.3f'
    cell = post_9d_metrics['C2_self_model_strength']
    row = '.3f'
    '.3f'
    cell = post_9d_metrics['plan_action_clip']
    'plan_noise_std'
    cell = '.3f'
    row = 'use_planning'
    'plan_horizon'
    row = '.3f'
    'wm_min_replay'['wm_beta_kl']
    row = list
    'wm_train_every'
    a = '+.3f'
    post_9d_metrics['plan_candidates']
    projection_calibration_metrics['wm_replay']
    'wm_optimizer'
    '+.3f'
    'critical_entropy'['world_model']
    'steps'
    round_projection_calibration['rollback_triggered']
    ' rollback='
    '.3f'
    round_projection_calibration['realized_projection_error']
    'env'
    '+.3f'
    round_projection_calibration['realized_gain']
    'agents'
    '.3f'
    round_projection_calibration['pred_rollback_risk_mean']
    ' pred_risk='
    '.3f'
    round_projection_calibration['pred_projection_error_mean']
    ' pred_proj='
    '+.3f'
    ('salt',)['pred_gain_mean']
    list
    1
    '+.3f'
    self_event_correlations[-1]
    ('dtype',)
    '+.3f'
    self_event_correlations[3,]
    3
    '+.3f'
    self_event_correlations[0]
    ('lr',)
    '+.3f'
    self_event_correlations['state_dim', 'action_dim', 'latent_dim', 'hidden_dim']
    '+.3f'
    self_event_correlations[0.01]
    'noise_scale'
    '+.3f'
    '  self correlation: with_self='[None]
    list
    ', after_gate='
    adopt_candidate_counts['adopt_candidates_final_adopt']
    ', final_adopt='
    adopt_candidate_counts['adopt_candidates_provisional']
    ', provisional='
    adopt_candidate_counts['adopt_candidates_after_gain']
    ', after_gain='
    adopt_candidate_counts['adopt_candidates_after_conf']
    ', after_conf='
    adopt_candidate_counts['adopt_candidates_after_post']
    ', after_post='
    ') adopt(raw='['adopt_candidates_raw']
    self_candidate_counts['self_candidates_after_persistence']
    ', after_persist='
    self_candidate_counts['self_candidates_after_conf']
    ', after_conf='
    self_candidate_counts['self_candidates_after_sz']
    ', after_sz='
    '  gate counts: self(raw='['self_candidates_raw']
    list
    tuple.mean(None, 3).ndarray()
    ' recur='
    tuple.mean(None, 4).ndarray()
    ' var='
    tuple.mean(None, 3).ndarray()
    ' ma='
    self_best_streak.ndarray()
    '  self persistence: streak='
    list
    if ('.4f' == 'none') == 'none':
        pass
    ', kl='
    '.4f'
    ', recon='
    '.4f'
    ' | wm(loss='
    '.3f'
    ' post_avg='
    '.3f'
    base_avg
    ' | base_avg='
    '03d'
    r
    'Round '
    list
    plan_noise_std(a['improvement_components'])
    ' '
    plan_horizon(a['confidence_components'])
    ' '
    '.3f'
    a.Adam('pred_rollback_risk', 1.0)
    ' pred_risk='
    '.3f'
    a.Adam('pred_projection_error', 0.0)
    ' pred_proj='
    '+.3f'
    a.Adam('pred_post_gain', 0.0)
    ' pred_gain='
    '.2f'
    a.Adam('rollback_rate', 0.0)
    ' rollback='
    '.3f'
    a.Adam('projection_error', 0.0)
    ' proj_err='
    a['threshold_mode']
    ' mode='
    '.3f'
    a['threshold_used']
    ' thresh='
    '.3f'
    a.Adam('selection_score', wm_hidden_dim('nan'))
    ' sel='
    '.3f'
    a.Adam('calibrated_projected', 0.0)
    ' proj_cal='
    '+.3f'
    a.Adam('raw_projected', 0.0)
    ' proj_raw='
    '.3f'
    a['calibrated_gain']
    ' gain_cal='
    '+.3f'
    a['raw_gain']
    ' gain_raw='
    '.3f'
    a['calibrated_confidence']
    ' conf_cal='
    '+.3f'
    a['raw_confidence']
    ': conf_raw='
    a['proposer']
    '<=P'
    a['agent']
    'A'
    []
    ''.wm_min_replay
    []
    plan_noise_std(a['improvement_components'])(', '.wm_min_replay)
    plan_horizon(a['confidence_components'])
    ' '
    '.3f'
    a['pred_rollback_risk']
    ' pred_risk='
    '.3f'
    a['pred_projection_error']
    ' pred_proj='
    '+.3f'
    a['pred_post_gain']
    ' pred_gain='
    '.2f'
    a['rollback_rate']
    ' rollback='
    '.3f'
    a['projection_error']
    ' proj_err='
    a['threshold_mode']
    ' mode='
    '.3f'
    a['threshold_used']
    ' thresh='
    '.3f'
    a['selection_score']
    ' sel='
    '.3f'
    a['calibrated_projected']
    ' proj_cal='
    '+.3f'
    a['raw_projected']
    ' proj_raw='
    '.3f'
    a['calibrated_gain']
    ' gain_cal='
    '+.3f'
    a['raw_gain']
    ' gain_raw='
    '.3f'
    a['calibrated_confidence']
    ' conf_cal='
    '+.3f'
    a['raw_confidence']
    ': conf_raw='
    a['proposer']
    '<=P'
    a['agent']
    'A'
    []
    ''.wm_min_replay
    0.0.adoption_realized_reward_decay
    gains_arr[adopted_mask]
    0.0
    gains_arr[adopted_mask]
    tuple.RSSMWorldModel
    self_event_any_history
    tuple.adoption_score_selection_conf_weight
    tuple.RSSMWorldModel
    self_adopted_any_history
    tuple.adoption_score_selection_conf_weight
    tuple.RSSMWorldModel
    realized_gain_history
    tuple.adoption_score_selection_conf_weight
    tuple(None(self_same_agent_recurrence_hits))
    wm_hidden_dim
    if tuple(None(self_same_agent_recurrence_trials)) == 0:
        pass
    social_conf_full_local_min
    wm_hidden_dim
    tuple._make_metrics_dict
    if (social_conf_full_local_min(self_same_agent_recurrence_trials[i]) == 0)(wm_hidden_dim[self_same_agent_recurrence_hits]) / wm_hidden_dim(self_same_agent_recurrence_trials[i]):
        pass
    use_planning(3)
    tuple.adoption_score_selection_conf_weight
    tuple._make_metrics_dict
    0.0
    -5
    hist
    wm_lr
    []
    self_score_history
    tuple.adoption_score_selection_conf_weight
    tuple._make_metrics_dict
    0.0
    -5
    hist
    []
    self_score_history
    tuple.adoption_score_selection_conf_weight
    self_event_any_history.adoption_realized_reward_decay
    self_best_streak
    0
    -1000000000.0
    -1000000000.0
    finite_self_scores
    tuple.wm_latent_dim
    tuple.RSSMWorldModel
    self_diag_scores
    tuple.adoption_score_selection_conf_weight
    realized_rollback_history
    projected_risk_history
    use_world_model
    wm_hidden_dim
    0.0(('default',))
    realized_projection_history
    projected_projection_history
    use_world_model
    wm_hidden_dim
    0.0(('default',))
    projected_realized_gain_history
    projected_gain_history
    use_world_model
    wm_hidden_dim
    []
    []
    []
    []
    []
    []
    wm_hidden_dim
    wm_hidden_dim('nan')(wm_hidden_dim)(wm_hidden_dim.Adam('projection_error', 0.0))
    wm_hidden_dim('nan')
    wm_hidden_dim('nan')
    wm_hidden_dim('nan')
    wm_hidden_dim('nan')
    wm_hidden_dim('nan')
    []
    'plan_candidates'.self_improve_persistence_floor
    'wm_beta_kl'.str
    'wm_min_replay'.decide_self_patch_adoption
    'wm_batch_size'.triad_propose_test_personal_dummies
    'wm_train_every'.append
    wm_replay
    'wm_replay'
    wm_optimizer
    'wm_optimizer'
    world_model
    'world_model'
    'critical_entropy'.enumerate
    'steps'.eval_kwargs
    restore_env
    'env'
    triad
    'agents'
    {}
    '+.3f'
    wm_candidate_projection_samples
    777
    r
    make_env_for
    'plan_horizon'.self_improve_patch_l2_hard
    'wm_beta_kl'.str
    'wm_min_replay'.decide_self_patch_adoption
    'wm_batch_size'.triad_propose_test_personal_dummies
    'wm_train_every'.append
    wm_replay
    'wm_replay'
    wm_optimizer
    'wm_optimizer'
    world_model
    'world_model'
    'critical_entropy'.enumerate
    'steps'.eval_kwargs
    post_env
    'env'
    triad
    'agents'
    {}
    '+.3f'
    wm_candidate_projection_samples
    777
    r
    make_env_for
    'pred_projection_error'
    'pred_post_gain'(wm_hidden_dim.Adam('pred_post_gain', 0.0))
    wm_hidden_dim(gain_detail.Adam('rollback_rate', 0.0))
    'rollback_rate'
    'projection_error'(wm_hidden_dim.Adam('projection_error', 0.0))
    'selection_score'(wm_hidden_dim)
    'base_selection_score'(wm_hidden_dim)
    'local_score'(wm_hidden_dim)
    'provisional'(copy.Adam('threshold_mode', 'base'))
    if 'threshold_mode' == 'provisional':
        pass
    'threshold_used'(wm_hidden_dim)
    wm_hidden_dim(proj_detail.Adam('calibrated_projected', 0.0))
    'calibrated_projected'
    'raw_projected'(wm_hidden_dim.Adam('raw_projected', 0.0))
    wm_hidden_dim(gain_detail.Adam('calibrated_gain', 0.0))
    'calibrated_gain'
    'raw_gain'(wm_hidden_dim.Adam('raw_gain', 0.0))
    wm_hidden_dim(conf_detail.Adam('calibrated_confidence', 0.0))
    'calibrated_confidence'
    'raw_confidence'(wm_hidden_dim.Adam('raw_confidence', 0.0))
    wm_hidden_dim(sz)
    'patch_size'
    'improvement'(wm_hidden_dim)
    proposer_j
    'proposer'
    agent_i
    'agent'
    {}
    '+.3f'
    _scale_patch
    'rollback_rate'.adoption_realized_reward_decay
    wm_hidden_dim(gain_detail.Adam('projection_error', 0.0))
    'projection_error'
    _scale_patch(proj_detail.Adam('components', {}))
    'projected_components'
    _scale_patch(gain_detail.Adam('components', {}))
    'improvement_components'
    _scale_patch(conf_detail.Adam('components', {}))
    'confidence_components'
    'selection_score'(wm_hidden_dim)
    'patch_size'(wm_hidden_dim[agent_i, proposer_j])
    'improvement'(wm_hidden_dim)
    'local_score'(wm_hidden_dim)
    copy(conf_detail.Adam('threshold_mode', 'base'))
    'threshold_mode'
    'threshold_used'(wm_hidden_dim)
    wm_hidden_dim(proj_detail.Adam('calibrated_projected', 0.0))
    'calibrated_projected'
    'raw_projected'(wm_hidden_dim.Adam('raw_projected', 0.0))
    wm_hidden_dim(gain_detail.Adam('calibrated_gain', 0.0))
    'calibrated_gain'
    'raw_gain'(wm_hidden_dim.Adam('raw_gain', 0.0))
    wm_hidden_dim(conf_detail.Adam('calibrated_confidence', 0.0))
    'calibrated_confidence'
    'raw_confidence'(wm_hidden_dim.Adam('raw_confidence', 0.0))
    'reason'(copy[agent_i][proposer_j])
    'proposer'
    'agent'
    {}
    '+.3f'
    _scale_patch
    'selection_score'.adoption_realized_reward_decay
    'patch_size'(wm_hidden_dim[agent_i, best_raw_j])
    'improvement'(wm_hidden_dim[agent_i, best_raw_j])
    wm_hidden_dim(best_conf.Adam('local_score', 0.0))
    'local_score'
    copy(best_conf.Adam('threshold_mode', 'base'))
    'threshold_mode'
    wm_hidden_dim(best_combined_full_threshold)
    'threshold_used'
    wm_hidden_dim(best_proj.Adam('calibrated_projected', 0.0))
    'calibrated_projected'
    wm_hidden_dim(best_proj.Adam('raw_projected', 0.0))
    'raw_projected'
    wm_hidden_dim(best_gain.Adam('calibrated_gain', 0.0))
    'calibrated_gain'
    wm_hidden_dim(best_gain.Adam('raw_gain', 0.0))
    'raw_gain'
    wm_hidden_dim(best_conf.Adam('calibrated_confidence', 0.0))
    'calibrated_confidence'
    wm_hidden_dim(best_conf.Adam('raw_confidence', 0.0))
    'raw_confidence'
    'reason'(copy[agent_i][best_raw_j])
    best_raw_j
    'proposer'
    agent_i
    'agent'
    {}
    '+.3f'
    _scale_patch
    wm_hidden_dim(projected_signal.Adam('pred_projection_error', 0.0)).adoption_realized_reward_decay
    'pred_projection_error'
    wm_hidden_dim(projected_signal.Adam('pred_post_gain', 0.0))
    'pred_post_gain'
    'available'(detach.Adam('available', False))
    {}
    '+.3f'
    _scale_patch
    _scale_patch(gain_signal['components'])
    wm_hidden_dim(gain_signal['rollback_rate'])
    wm_hidden_dim(gain_signal['projection_error'])
    wm_hidden_dim(gain_signal['provisional_threshold'])(wm_hidden_dim)(wm_hidden_dim)
    _scale_patch(wm_hidden_dim)(wm_hidden_dim)(wm_hidden_dim['full_threshold'])
    _scale_patch(confidence['components'])(wm_hidden_dim)(wm_hidden_dim)
    wm_hidden_dim(confidence['full_threshold'])(wm_hidden_dim(confidence['provisional_threshold'])(copy(confidence['threshold_mode'])(wm_hidden_dim)(wm_hidden_dim), social_conf_full_local_min))(wm_hidden_dim)
    _scale_patch(wm_hidden_dim)(wm_hidden_dim)
    tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict
    wm_hidden_dim('nan')
    (3, 3)
    tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict
    wm_hidden_dim('nan')
    (3, 3)
    tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict
    wm_hidden_dim('nan')
    (3, 3)
    tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict
    -1000000000.0
    (3, 3)
    tuple.adaptive_patch_goal_mse_hard
    tuple._make_metrics_dict
    'score_matrix'(tuple.mean, None((3, 3)))
    _dummy_logs.Adam
    tuple.adoption_score_selection_conf_weight
    tuple._make_metrics_dict
    patch_sizes
    tuple.adoption_score_selection_conf_weight
    tuple._make_metrics_dict
    improvements
    tuple.adoption_score_selection_conf_weight
    wm_candidate_pred_gain_min_full
    _clip01
    tuple.adoption_score_selection_conf_weight
    tuple._compute_social_confidence
    wm_hidden_dim
    items(baseline_score, (is_tensor, adaptive_patch_scale_min, tuple._safe_mean_arr))
    'plan_action_clip'.random
    'plan_noise_std'.max
    'plan_candidates'.self_improve_persistence_floor
    'plan_horizon'.self_improve_patch_l2_hard
    'wm_beta_kl'.str
    'wm_min_replay'.decide_self_patch_adoption
    'wm_batch_size'.triad_propose_test_personal_dummies
    'wm_train_every'.append
    wm_replay
    'wm_replay'
    wm_optimizer
    'wm_optimizer'
    world_model
    'world_model'
    'critical_entropy'.enumerate
    'steps'.wm_candidate_projection_gamma
    base_env
    'env'
    triad
    'agents'
    {}
    '+.3f'
    wm_candidate_projection_samples
    0
    r
    make_env_for
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._compute_goal_pressure
    -1
    (3,)
    tuple.adaptive_patch_goal_mse_hard
    tuple._compute_goal_pressure
    (3,)
    tuple.mean
    tuple._compute_goal_pressure
    (3,)
    tuple.mean
    tuple._compute_goal_pressure
    (3,)
    tuple.mean
    tuple._compute_goal_pressure
    (3,)
    tuple.mean
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean
    tuple._compute_goal_pressure
    (3,)
    tuple.mean
    tuple._make_metrics_dict
    (3,)
    tuple.mean

import __future__
annotations = annotations
__future__
import dataclasses
dataclass = dataclass
field = field
dataclasses
import typing
Any = Any
Dict = Dict
List = List
Tuple = Tuple
Optional = Optional
typing
import numpy
np = numpy
import torch
torch = torch
import agents.memory_agent
MemoryConsciousAgent = MemoryConsciousAgent
agents.memory_agent
import agents.proposal_net
ProposalNet = ProposalNet
ProposalNetConfig = ProposalNetConfig
agents.proposal_net
import agents.self_improvement
SelfImprovementConfig = SelfImprovementConfig
agents.self_improvement
import agents.world_model
RSSMWorldModel = RSSMWorldModel
agents.world_model
import theory.nined_core
NineDLayout = NineDLayout
theory.nined_core
import evolution.multi_agent_eval_comms
evaluate_group_with_comms = evaluate_group_with_comms
evolution.multi_agent_eval_comms
import evolution.triad_propose_personal_dummies
triad_propose_test_personal_dummies = triad_propose_test_personal_dummies
summarize_logs = summarize_logs
_adopt_patch_raw = adopt_patch
evolution.triad_propose_personal_dummies
SimpleTriadEnv = __build_class__(None, 'SimpleTriadEnv')
ProposalLearningConfig = __build_class__(None, 'ProposalLearningConfig')()

torch
('action', 'state_batch', 'instability')
0.0
(0.0,)
(None('nan'),)
float
(0.0,)
(0.0,)
(0.0,)
dataclass