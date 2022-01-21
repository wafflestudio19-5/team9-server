from rest_framework import serializers


class PostCreateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True, help_text="main post의 content")
    scope = serializers.IntegerField(required=True, help_text="공개범위 설정: 1(자기 자신), 2(친구), 3(전체 공개)")
    tagged_users = serializers.ListField(child=serializers.IntegerField(), required=False, help_text="태그된 유저들의 id의 array")
    subposts_tagged_users = serializers.ListField(required=False, help_text="subpost별로 태그된 유저들의 id의 array들의 array (nested array)")


class PostUpdateSwaggerSerializer(PostCreateSwaggerSerializer):
    subposts = serializers.ListField(child=serializers.CharField(), required=False, help_text="subpost들의 content의 array")
    subposts_id = serializers.ListField(child=serializers.IntegerField(), required=False, help_text="기존 subpost들의 id의 array")
    removed_subposts = serializers.ListField(child=serializers.IntegerField(), required=False, help_text="삭제될 subpost들의 id의 array")


class CommentCreateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    parent = serializers.IntegerField(
        required=False, help_text="부모 댓글의 id. Depth가 0인 경우 해당 필드를 비워두세요."
    )
    tagged_users = serializers.ListField(child=serializers.IntegerField(), required=False)


class CommentUpdateSwaggerSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)
    tagged_users = serializers.ListField(child=serializers.IntegerField(), required=False)