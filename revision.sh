#!/bin/sh

usage()
{
    echo "usage: $(basename $0) (-d | <base version> [<version suffix>])" >&2
    exit $1
}

func=revision
while getopts dh f; do
    case $f in
        d)
            func=date
            ;;

        h)
            usage 0
            ;;

        *)
            usage 1
            ;;
    esac
done
shift $(($OPTIND - 1))

case $func in
    revision)
        if [ $# -lt 1 -o $# -gt 2 ]; then
            usage 1
        fi
        ;;

    date)
        if [ $# -gt 0 ]; then
            usage 1
        fi
        ;;

    *)
        usage 1
        ;;
esac

_revision()
{
    if [ -r .version ]; then
        cat .version
    else
        echo $1$2
    fi
}

git_revision()
{
    local ver versuffix describe untagged commits branch sha dirty

    ver=$1
    versuffix=$2

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

    echo ${ver}${versuffix}${untagged}${commits}${branch}${sha}${dirty}
}

svn_revision()
{
    local ver versuffix tagrev untagged commits rev dirty

    ver=$1
    versuffix=$2

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

    echo ${ver}${versuffix}${untagged}${commits}${rev}${dirty}
}

_date()
{
    if [ -r .version.date ]; then
        cat .version.date
    else
        date '+%Y%m%d'
    fi
}

git_date()
{
    local date

    if git diff --quiet; then
        date=$(git log -1 --format='%ci' | \
            awk '{gsub("-", "", $1); print $1}')
    else
        date=$(_date)
    fi

    echo $date
}

svn_date()
{
    local date

    if ! (svn status -q | grep -q .); then
        date=$(svn log -q --limit 1 | \
            awk '/^r[0-9]+/ {gsub("-", "", $5); print $5}')
    else
        date=$(_date)
    fi

    echo $date
}

repo=""
if test -d .git || git rev-parse --git-dir > /dev/null 2>&1; then
    repo=git
elif test -d .svn || svn info > /dev/null 2>&1; then
    repo=svn
fi

${repo}_${func} "$@"
