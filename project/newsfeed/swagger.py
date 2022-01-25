from rest_framework import serializers


class PostCreateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, help_text="mainpost의 content")
    scope = serializers.IntegerField(
        required=True, help_text="공개범위 설정: 1(자기 자신), 2(친구), 3(전체 공개)"
    )
    tagged_users = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="`[mainpost에 태그된 유저들의 id]`"
    )
    subposts = serializers.ListField(
        child=serializers.CharField(), required=False, help_text="각 subpost에 대한 정보를 담은 array\n`[{\"content\": (해당 subpost의 content), \"tagged_users\": [해당 subpost에 tag된 user들의 id]}]`"
    )


class PostUpdateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, help_text="mainpost의 수정할 content.\n수정 사항이 없을 시 이전 content 그대로")
    scope = serializers.IntegerField(
        required=False, help_text="공개범위 수정: 1(자기 자신), 2(친구), 3(전체 공개)"
    )
    tagged_users = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="`[mainpost에 태그된 유저들의 id]`\n수정 사항이 없을 시 이전 tagged_users 그대로"
    )

    subposts = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text="수정하려는 각 subpost의 정보를 담은 array\n`[{\"id\": (수정할 subpost의 id), \"content\": (해당 subpost의 content), \"tagged_users\": [해당 subpost에 tag된 user들의 id]}]`\n포함된 각 subpost에 대하여 content 혹은 tagged_users의 수정 사항이 없을 시 이전 내용과 그대로",
    )

    new_subposts = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="추가할 subpost subpost의 정보를 담은 array\n`[{\"content\": (해당 subpost의 content), \"tagged_users\": [해당 subpost에 tag된 user들의 id]}]`",
    )

    removed_subposts = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="`[삭제될 subpost들의 id]`",
    )


class CommentCreateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    parent = serializers.IntegerField(
        required=False, help_text="부모 댓글의 id. Depth가 0인 경우 해당 필드를 비워두세요."
    )
    tagged_users = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )


class CommentUpdateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    tagged_users = serializers.ListField(
        child=serializers.IntegerField(), required=False
    )
