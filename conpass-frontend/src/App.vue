<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AiChatWidget from './components/AiChatWidget.vue'

const auth = useAuthStore()
</script>

<template>
  <RouterView />
  <AiChatWidget v-if="auth.isLoggedIn" />
</template>
