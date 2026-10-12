// Draft releases are discoverable through the collection and release ID, but
// GitHub's by-tag endpoint can return 404 until the release is public.
module.exports = async function finalizeRelease({ github, context, tag, expectedAssets }) {
  const repo = { owner: context.repo.owner, repo: context.repo.repo };
  const releases = await github.paginate(github.rest.repos.listReleases, { ...repo, per_page: 100 });
  const found = releases.find(release => release.tag_name === tag);
  if (!found) throw new Error(`No release for ${tag}`);
  const { data: release } = await github.rest.repos.getRelease({ ...repo, release_id: found.id });
  const assets = release.assets.filter(asset => asset.state === 'uploaded' && asset.size > 0);
  for (const name of [`MDCx-${tag}-windows-x86_64.exe`, `MDCx-${tag}-macos-aarch64.dmg`, `MDCx-${tag}-SHA256SUMS.txt`]) {
    const asset = assets.find(item => item.name === name);
    if (!asset) throw new Error(`Missing validated asset: ${name}`);
    if (expectedAssets && asset.digest !== `sha256:${expectedAssets[name]}`) {
      throw new Error(`Asset checksum mismatch: ${name}`);
    }
  }
  await github.rest.repos.updateRelease({ ...repo, release_id: release.id, draft: false, prerelease: false, make_latest: 'true' });
  if (tag === 'v1.1.0') {
    const legacy = releases.find(item => item.tag_name === '220261012');
    if (legacy) {
      const notice = `> 此日期编号版已由 [MDCx ${tag}](https://github.com/${repo.owner}/${repo.repo}/releases/tag/${tag}) 替代。正式版本沿用 v1.x.x。请下载新成品，沿用原配置；旧程序的整数更新检查不能解析新标签，需要手动替换一次。\n\n`;
      const body = (legacy.body || '').startsWith(notice) ? legacy.body : notice + (legacy.body || '');
      await github.rest.repos.updateRelease({ ...repo, release_id: legacy.id, name: '[已替代] MDCx 220261012', prerelease: true, make_latest: 'false', body });
    }
  }
};
