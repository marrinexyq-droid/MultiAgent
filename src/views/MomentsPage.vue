<template>
  <div class="moments-page">
    <!-- Profile Card -->
    <div class="profile-card">
      <div class="banner">
        <img src="https://picsum.photos/800/300?random=1" alt="banner" />
      </div>
      <div class="profile-info">
        <div class="avatar">
          <img src="https://picsum.photos/100/100?random=2" alt="avatar" />
        </div>
        <div class="username">XX科技</div>
        <div class="stats">
          <span>发稿 215</span>
          <span class="divider">|</span>
          <span>关注 22</span>
          <span class="divider">|</span>
          <span>粉丝 343</span>
        </div>
      </div>
    </div>

    <!-- Moments List -->
    <div class="moments-list">
      <div class="moment-item" v-for="(moment, index) in moments" :key="index">
        <div class="moment-header">
          <img :src="moment.avatar" class="moment-avatar" />
          <div class="moment-info">
            <div class="moment-name">{{ moment.name }}</div>
            <div class="moment-meta">
              <span class="time">{{ moment.time }}</span>
              <span class="location" v-if="moment.location">
                <i class="icon-location">📍</i>
                {{ moment.location }}
              </span>
            </div>
          </div>
        </div>

        <div class="moment-content">
          <p>{{ moment.content }}</p>
        </div>

        <div class="moment-images" v-if="moment.images && moment.images.length">
          <div 
            class="image-grid" 
            :class="'grid-' + Math.min(moment.images.length, 4)"
          >
            <img 
              v-for="(img, imgIndex) in moment.images.slice(0, 9)" 
              :key="imgIndex" 
              :src="img" 
              class="moment-image"
            />
          </div>
        </div>

        <div class="moment-footer">
          <div class="likes" v-if="moment.likes && moment.likes.length">
            <span class="like-icon">👍</span>
            <div class="likers">
              <span 
                v-for="(liker, li) in moment.likes" 
                :key="li" 
                class="liker"
              >
                {{ liker }}
              </span>
            </div>
          </div>

          <div class="comments" v-if="moment.comments && moment.comments.length">
            <div 
              class="comment" 
              v-for="(comment, ci) in moment.comments" 
              :key="ci"
            >
              <span class="commenter">{{ comment.user }}:</span>
              <span class="comment-text">{{ comment.text }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const moments = [
  {
    avatar: 'https://picsum.photos/60/60?random=10',
    name: 'XX科技',
    time: '2小时前',
    location: '深圳南山区',
    content: '今天天气真好，适合出去走走！顺便测试一下新功能，看看效果如何。',
    images: [
      'https://picsum.photos/300/300?random=20',
      'https://picsum.photos/300/300?random=21',
      'https://picsum.photos/300/300?random=22',
      'https://picsum.photos/300/300?random=23',
    ],
    likes: ['张三', '李四', '王五', '赵六', '钱七'],
    comments: [
      { user: '张三', text: '拍得真好看！' },
      { user: '李四', text: '这地方我也去过~' },
    ],
  },
  {
    avatar: 'https://picsum.photos/60/60?random=11',
    name: 'XX科技',
    time: '昨天',
    location: '',
    content: '新项目启动，期待和大家合作！有需要的朋友可以联系我。',
    images: [
      'https://picsum.photos/300/300?random=30',
      'https://picsum.photos/300/300?random=31',
    ],
    likes: ['小明', '小红', '大白'],
    comments: [
      { user: '小明', text: '支持！' },
    ],
  },
  {
    avatar: 'https://picsum.photos/60/60?random=12',
    name: 'XX科技',
    time: '3天前',
    location: '广州天河区',
    content: '周末加班完成了一个重要的功能模块，虽然辛苦但很有成就感。继续加油！',
    images: [
      'https://picsum.photos/300/300?random=40',
      'https://picsum.photos/300/300?random=41',
      'https://picsum.photos/300/300?random=42',
    ],
    likes: ['同事A', '同事B', '同事C', '同事D'],
    comments: [
      { user: '同事A', text: '辛苦了！' },
      { user: '同事B', text: '效率真高！' },
      { user: '同事C', text: '膜拜大神！' },
    ],
  },
  {
    avatar: 'https://picsum.photos/60/60?random=13',
    name: 'XX科技',
    time: '上周',
    location: '',
    content: '分享一篇好文章：关于AI的未来发展趋势，深度好文，值得一读！',
    images: [],
    likes: ['读者1', '读者2'],
    comments: [
      { user: '读者1', text: '已收藏，谢谢分享！' },
      { user: '读者2', text: '这篇文章确实不错' },
    ],
  },
  {
    avatar: 'https://picsum.photos/60/60?random=14',
    name: 'XX科技',
    time: '2周前',
    location: '北京朝阳区',
    content: '参加了一场技术大会，收获满满，见到了很多业界大牛，学到了很多新技术理念。',
    images: [
      'https://picsum.photos/300/300?random=50',
      'https://picsum.photos/300/300?random=51',
      'https://picsum.photos/300/300?random=52',
      'https://picsum.photos/300/300?random=53',
      'https://picsum.photos/300/300?random=54',
      'https://picsum.photos/300/300?random=55',
    ],
    likes: ['网友A', '网友B', '网友C', '网友D', '网友E', '网友F'],
    comments: [
      { user: '网友A', text: '真羡慕能参加大会！' },
      { user: '网友B', text: '求分享大会PPT~' },
    ],
  },
]
</script>

<style scoped>
.moments-page {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 20px;
}

.profile-card {
  background: #fff;
  margin-bottom: 10px;
}

.banner {
  height: 200px;
  overflow: hidden;
  position: relative;
}

.banner img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.profile-info {
  padding: 0 20px 20px;
  position: relative;
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  border: 3px solid #fff;
  overflow: hidden;
  position: absolute;
  top: -40px;
  left: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.username {
  font-size: 22px;
  font-weight: 600;
  color: #333;
  margin-top: 45px;
  margin-bottom: 8px;
}

.stats {
  font-size: 14px;
  color: #666;
}

.stats .divider {
  margin: 0 12px;
  color: #ddd;
}

.moments-list {
  padding: 0 10px;
}

.moment-item {
  background: #fff;
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 10px;
}

.moment-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 12px;
}

.moment-avatar {
  width: 44px;
  height: 44px;
  border-radius: 4px;
  margin-right: 12px;
  object-fit: cover;
}

.moment-info {
  flex: 1;
}

.moment-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a1a;
  margin-bottom: 4px;
}

.moment-meta {
  font-size: 13px;
  color: #999;
}

.moment-meta .location {
  margin-left: 10px;
}

.moment-meta .icon-location {
  font-style: normal;
  font-size: 12px;
}

.moment-content {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
  margin-bottom: 12px;
  word-break: break-word;
}

.moment-content p {
  margin: 0;
}

.moment-images {
  margin-bottom: 12px;
}

.image-grid {
  display: grid;
  gap: 4px;
}

.image-grid.grid-1 {
  grid-template-columns: 1fr;
  max-width: 200px;
}

.image-grid.grid-2 {
  grid-template-columns: repeat(2, 1fr);
  max-width: 300px;
}

.image-grid.grid-3 {
  grid-template-columns: repeat(3, 1fr);
}

.image-grid.grid-4 {
  grid-template-columns: repeat(2, 1fr);
}

.moment-image {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
  transition: transform 0.2s;
}

.moment-image:hover {
  transform: scale(1.02);
}

.moment-footer {
  border-top: 1px solid #f0f0f0;
  padding-top: 12px;
}

.likes {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.like-icon {
  font-size: 14px;
}

.likers {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.liker {
  color: #576b95;
  font-size: 14px;
  cursor: pointer;
}

.liker:not(:last-child)::after {
  content: '、';
  color: #576b95;
}

.comments {
  background: #f7f7f7;
  border-radius: 4px;
  padding: 8px 10px;
}

.comment {
  font-size: 14px;
  line-height: 1.5;
  color: #333;
}

.commenter {
  color: #576b95;
  cursor: pointer;
}

.comment-text {
  color: #333;
}
</style>