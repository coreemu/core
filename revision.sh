#!/bin/sh

if [ $# -ne 1 ]; then
    echo "usage: $(basename $0) <base version>" >&2
    exit 1
fi

git_revision()
{
    local ver describe untagged commits branch sha dirty

    ver=$1

    describe=$(git describe --tags --dirty  2> /dev/null)
    if [ "$describe" ]; then
        echo "$describe" | sed -e 's/^release-//'
        return
    fi

    if [ ! "$(git tag -l release-$ver)" ]; then
        untagged=".untagged"
    else
        commits=$(git rev-list release-${ver}^..HEAD | wc -l)
        if [ $commits -eq 0 ]; then
            commits=""
        else
            commits=".$commits"
        fi
    fi

    branch=$(git rev-parse --abbrev-ref HEAD)
    if [ "$branch" = master ]; then
        branch=""
    else
        branch=".$(echo -n $branch | tr -sC '.[:alnum:]' '[.*]')"
    fi

    if [ "$untagged" -o "$commits" ]; then
        sha=.g$(git log -1 --pretty="%h")
    fi

    if ! git diff --quiet; then
        dirty=".dirty"
    else
        dirty=""
    fi

    echo ${ver}${untagged}${commits}${branch}${sha}${dirty}
}

svn_revision()
{
    local ver tagrev untagged commits rev dirty

    ver=$1

    tagrev=$(svn log -q ^/tags/release-$ver --limit 1 2> /dev/null | \
        awk '/^r/ {print $1}')
    if [ ! "$tagrev" ];then
        untagged=".untagged"
    else
        commits=$(svn log -q -r $tagrev:HEAD | grep '^r' | wc -l)
        if [ $commits -eq 0 ]; then
            commits=""
        else
            commits=".$commits"
        fi
    fi

    if [ "$untagged" -o "$commits" ]; then
        rev=.s$(svn info | awk '/^Revision:/ {print $2}')
    fi

    if (svn status -q | grep -q .); then
        dirty=".dirty"
    fi

    echo ${ver}${untagged}${commits}${rev}${dirty}
}

if test -d .git || git rev-parse --git-dir > /dev/null 2>&1; then
    git_revision "$@"
elif test -d .svn || svn info > /dev/null 2>&1; then
    svn_revision "$@"
else
    echo "$@"
fi
