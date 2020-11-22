import datetime
import pathlib
import plistlib
import os
import shutil
import subprocess
import ctypes

if os.environ['ENABLE_ON_DEMAND_RESOURCES'] == 'YES':
    raise Exception('This script collides with Xcode\'s ODR processing')

def main():
    root = pathlib.Path(os.environ['SRCROOT'])/'deps'/'aports'
    repo_path = root/'main'/'x86'
    packs = []
    for file in repo_path.iterdir():
        rsrc = ':'.join(file.relative_to(root).parts)
        packs.append(([rsrc], {rsrc: str(file)}))
    print('collected packs')
    process_odrs(packs)

# packs: [([tag], {resource_name: file_name}])]
# OnDemandResources.plist: {
#   NSBundleResourceRequestTags: {tag: [asset_pack]}
#   NSBundleResourceRequestAssetPacks: {asset_pack: [filename]}
# }
# AssetPackManifestTemplate.plist: [{'bundleKey': asset_pack, 'URL': url}]
def process_odrs(packs):
    target_build_dir = pathlib.Path(os.environ['TARGET_BUILD_DIR'])
    resources_dir = target_build_dir/os.environ['UNLOCALIZED_RESOURCES_FOLDER_PATH']
    odrs_dir = target_build_dir/'OnDemandResources'
    odrs_dir.mkdir(exist_ok=True)

    packs = [(gen_pack_id(tags), tags, files) for (tags, files) in packs]
    odr_tags_plist = {}
    odr_packs_plist = {}
    odrs_plist = {
        'NSBundleResourceRequestTags': odr_tags_plist,
        'NSBundleResourceRequestAssetPacks': odr_packs_plist,
    }
    packs_manifest_plist = {'resources': []}
    for pack_id, tags, files in packs:
        for tag in tags:
            if tag not in odr_tags_plist:
                odr_tags_plist[tag] = {'NSAssetPacks': []}
            odr_tags_plist[tag]['NSAssetPacks'].append(pack_id)
        odr_packs_plist[pack_id] = list(files.keys())

        pack_path = odrs_dir/(pack_id+'.assetpack')
        if pack_path.exists():
            shutil.rmtree(pack_path)
        pack_path.mkdir()
        total_size = 0
        with (pack_path/'Info.plist').open('wb') as f:
            plistlib.dump({
                'CFBundleIdentifier': pack_id,
                'Tags': tags,
            }, f, fmt=plistlib.FMT_BINARY)
            total_size += f.tell()
        newest_mtime = 0
        for file, file_src in files.items():
            if not os.path.isabs(file_src):
                file_src = os.path.join(os.environ['SRCROOT'], file_src)
            file_stat = os.stat(file_src)
            total_size += file_stat.st_size
            if newest_mtime < file_stat.st_mtime:
                newest_mtime = file_stat.st_mtime
            copy_file(pathlib.Path(file_src), pack_path/file)
        packs_manifest_plist['resources'].append({
            'URL': f'http://127.0.0.1{pack_path.resolve()}',
            'bundleKey': pack_id,
            'isStreamable': True,
            'primaryContentHash': {
                'hash': datetime.datetime.fromtimestamp(newest_mtime).isoformat(),
                'strategy': 'modtime',
            },
            'uncompressedSize': total_size,
        })

    with (resources_dir/'OnDemandResources.plist').open('wb') as f:
        plistlib.dump(odrs_plist, f, fmt=plistlib.FMT_BINARY)
    with (resources_dir/'AssetPackManifestTemplate.plist').open('wb') as f:
        plistlib.dump(packs_manifest_plist, f, fmt=plistlib.FMT_BINARY)

def gen_pack_id(tags):
    bundle_id = os.environ['PRODUCT_BUNDLE_IDENTIFIER']
    return bundle_id + '.asset.' + '+'.join(tags)

def copy_file(src, dst):
    # apfs clone?
    try:
        clonefile = ctypes.CDLL(None, use_errno=True).clonefile
        clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    except Exception:
        raise
        shutil.copyfile(src, dst)
        return
    res = clonefile(bytes(src), bytes(dst), 0)
    if res == -1 and ctypes.get_errno() != 0:
        raise os.OSError(ctypes.get_errno())

if __name__ == '__main__':
    main()
