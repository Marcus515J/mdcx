const assert = require('node:assert/strict');
const test = require('node:test');
const finalize = require('./finalize-release.cjs');

function fixture() {
  const names = ['windows-x86_64.exe', 'macos-aarch64.dmg', 'SHA256SUMS.txt'].map(suffix => `MDCx-v1.1.0-${suffix}`);
  const release = { id: 1, tag_name: 'v1.1.0', draft: true, assets: names.map(name => ({ name, state: 'uploaded', size: 100, digest: 'sha256:known' })) };
  const legacy = { id: 2, tag_name: '220261012', body: 'Historical release notes' };
  const updates = [];
  const repos = {
    listReleases: () => {},
    getRelease: async ({ release_id }) => { assert.equal(release_id, 1); return { data: release }; },
    getReleaseByTag: async () => { throw new Error('Draft by-tag lookup returns 404'); },
    updateRelease: async update => { updates.push(update); if (update.release_id === 2) legacy.body = update.body; }
  };
  return {
    release, legacy, updates,
    args: { github: { paginate: async () => [release, legacy], rest: { repos } }, context: { repo: { owner: 'Marcus515J', repo: 'mdcx' } }, tag: 'v1.1.0' }
  };
}

test('publishes a complete draft by ID and retires the date release', async () => {
  const f = fixture();
  await finalize(f.args);
  assert.equal(f.updates[0].release_id, 1);
  assert.equal(f.updates[0].draft, false);
  assert.equal(f.updates[0].make_latest, 'true');
  assert.equal(f.updates[1].prerelease, true);
  assert.ok(f.updates[1].body.endsWith('Historical release notes'));
});

test('refuses an incomplete release before publishing', async () => {
  const f = fixture();
  f.release.assets.pop();
  await assert.rejects(finalize(f.args), /Missing validated asset/);
  assert.equal(f.updates.length, 0);
});

test('recovery refuses changed asset digests', async () => {
  const f = fixture();
  await assert.rejects(finalize({ ...f.args, expectedAssets: {} }), /checksum mismatch/);
  assert.equal(f.updates.length, 0);
});

test('retrying finalization does not duplicate the migration notice', async () => {
  const f = fixture();
  await finalize(f.args);
  const body = f.legacy.body;
  await finalize(f.args);
  assert.equal(f.legacy.body, body);
});
