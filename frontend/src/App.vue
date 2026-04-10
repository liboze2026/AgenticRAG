<template>
  <el-container style="height: 100vh">
    <el-aside width="200px">
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/documents">
          <span>文档管理</span>
        </el-menu-item>
        <el-menu-item index="/datasets">
          <span>数据集</span>
        </el-menu-item>
        <el-menu-item index="/query">
          <span>检索问答</span>
        </el-menu-item>
        <el-menu-item index="/experiments">
          <span>实验工作台</span>
        </el-menu-item>
        <el-menu-item index="/system">
          <span>系统状态</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
