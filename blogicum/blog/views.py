from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView
)

from .constants import POSTS_PER_PAGE
from .forms import CommentForm, PostForm, ProfileForm
from .models import Category, Comment, Post

User = get_user_model()


def get_posts(queryset=None, only_published=True, with_comments=True):
    """Посты со связанными объектами.

    only_published — только опубликованные посты из опубликованных
    категорий с датой не в будущем; with_comments — добавить число
    комментариев (comment_count) и отсортировать от новых к старым.
    """
    if queryset is None:
        queryset = Post.objects.all()
    queryset = queryset.select_related('author', 'category', 'location')
    if only_published:
        queryset = queryset.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        )
    if with_comments:
        queryset = queryset.annotate(
            comment_count=Count('comments')
        ).order_by(*Post._meta.ordering)
    return queryset


class OnlyAuthorMixin:
    """Пускает к посту только автора, остальных — на страницу поста."""

    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = get_object_or_404(Post, pk=kwargs[self.pk_url_kwarg])
        if post.author != request.user:
            return redirect('blog:post_detail', post_id=post.pk)
        return super().dispatch(request, *args, **kwargs)


class IndexView(ListView):
    template_name = 'blog/index.html'
    paginate_by = POSTS_PER_PAGE

    def get_queryset(self):
        return get_posts()


class CategoryPostsView(ListView):
    template_name = 'blog/category.html'
    paginate_by = POSTS_PER_PAGE

    def get_queryset(self):
        self.category = get_object_or_404(
            Category, slug=self.kwargs['category_slug'], is_published=True
        )
        return get_posts(self.category.posts)

    def get_context_data(self, **kwargs):
        return super().get_context_data(category=self.category, **kwargs)


class ProfileView(ListView):
    template_name = 'blog/profile.html'
    paginate_by = POSTS_PER_PAGE

    def get_queryset(self):
        self.profile = get_object_or_404(
            User, username=self.kwargs['username']
        )
        return get_posts(
            self.profile.posts,
            only_published=self.request.user != self.profile,
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(profile=self.profile, **kwargs)


class ProfileEditView(LoginRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = 'blog/user.html'

    def get_object(self, queryset=None):
        return self.request.user

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user.username,))


class PostDetailView(DetailView):
    template_name = 'blog/detail.html'
    pk_url_kwarg = 'post_id'

    def get_object(self, queryset=None):
        post = get_object_or_404(
            get_posts(only_published=False, with_comments=False),
            pk=self.kwargs[self.pk_url_kwarg],
        )
        if post.author == self.request.user:
            return post
        return get_object_or_404(
            get_posts(with_comments=False),
            pk=self.kwargs[self.pk_url_kwarg],
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=CommentForm(),
            comments=self.object.comments.select_related('author'),
            **kwargs,
        )


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user.username,))


class PostUpdateView(OnlyAuthorMixin, LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        return reverse('blog:post_detail', args=(self.object.pk,))


class PostDeleteView(OnlyAuthorMixin, LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            form=PostForm(instance=self.object), **kwargs
        )

    def get_success_url(self):
        return reverse('blog:profile', args=(self.request.user.username,))


class CommentCreateView(LoginRequiredMixin, CreateView):
    model = Comment
    form_class = CommentForm

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.post = get_object_or_404(
            get_posts(with_comments=False), pk=self.kwargs['post_id']
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:post_detail', args=(self.kwargs['post_id'],))


class CommentMixin(LoginRequiredMixin):
    """Только свой комментарий к указанному посту, иначе 404."""

    model = Comment
    template_name = 'blog/comment.html'
    pk_url_kwarg = 'comment_id'

    def get_queryset(self):
        return Comment.objects.filter(
            author=self.request.user, post_id=self.kwargs['post_id']
        )

    def get_success_url(self):
        return reverse('blog:post_detail', args=(self.kwargs['post_id'],))


class CommentUpdateView(CommentMixin, UpdateView):
    form_class = CommentForm


class CommentDeleteView(CommentMixin, DeleteView):
    pass
