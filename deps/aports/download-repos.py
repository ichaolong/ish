#!/usr/bin/env python3
import tqdm
import urllib.request
import urllib.parse
import tarfile
import pathlib
import concurrent.futures

IX_NAME = 'P'
IX_VERSION = 'V'

def read_index(index):
    pkgs = []
    pkg = {}
    while True:
        line = index.readline()
        oline = line
        if line == b'\n':
            pkgs.append(pkg)
            pkg = {}
            continue
        if line == b'':
            break
        assert line.endswith(b'\n')
        line = line[:-1]

        key, _, value = line.partition(b':')
        pkg[key.decode()] = value.decode()
    return pkgs

def download_repo(root_url, repo_name, index_name):
    repo = pathlib.Path(repo_name)
    repo.mkdir(parents=True, exist_ok=True)
    index_path = repo/'APKINDEX.tar.gz'
    index_url = f'{root_url}/{repo_name}/{index_name}'
    urllib.request.urlretrieve(index_url, index_path)
    with tarfile.open(index_path) as tar:
        pkgs = read_index(tar.extractfile('APKINDEX'))

    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as pool:
        futures = [pool.submit(download_package, repo, f'{root_url}/{repo_name}', pkg) for pkg in pkgs]
        for f in tqdm.tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
            f.result()

def download_package(repo, root_url, pkg):
    pkg_file = f'{pkg[IX_NAME]}-{pkg[IX_VERSION]}.apk'
    url = f'{root_url}/{urllib.parse.quote(pkg_file)}'
    path = repo/pkg_file
    if path.exists(): return
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as e:
        print('failed to download', url, ':', e)
        raise
    return pkg

if __name__ == '__main__':
    download_repo('https://f001.backblazeb2.com/file/alpine-archive', 'main/x86', 'APKINDEX-v3.12-2020-11-15.tar.gz')
