#!/bin/sh
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create schemas for each service
    CREATE SCHEMA IF NOT EXISTS auth;
    CREATE SCHEMA IF NOT EXISTS users;
    CREATE SCHEMA IF NOT EXISTS posts;
    CREATE SCHEMA IF NOT EXISTS comments;
    CREATE SCHEMA IF NOT EXISTS likes;
    
    -- Enable UUID extension
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    
    -- Grant permissions
    GRANT ALL ON SCHEMA auth TO $POSTGRES_USER;
    GRANT ALL ON SCHEMA users TO $POSTGRES_USER;
    GRANT ALL ON SCHEMA posts TO $POSTGRES_USER;
    GRANT ALL ON SCHEMA comments TO $POSTGRES_USER;
    GRANT ALL ON SCHEMA likes TO $POSTGRES_USER;
    
    -- Auth Service Tables
    CREATE TABLE IF NOT EXISTS auth.users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT true,
        is_verified BOOLEAN DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
        token VARCHAR(255) UNIQUE NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMP WITH TIME ZONE
    );
    
    -- User Service Tables
    CREATE TABLE IF NOT EXISTS users.profiles (
        user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
        username VARCHAR(50) UNIQUE NOT NULL,
        display_name VARCHAR(100),
        bio TEXT,
        avatar_url VARCHAR(500),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Post Service Tables
    CREATE TABLE IF NOT EXISTS posts.posts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        author_id UUID NOT NULL,
        title VARCHAR(255) NOT NULL,
        slug VARCHAR(255) UNIQUE NOT NULL,
        content TEXT NOT NULL,
        summary VARCHAR(500),
        status VARCHAR(20) DEFAULT 'draft',
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        published_at TIMESTAMP WITH TIME ZONE
    );
    
    CREATE TABLE IF NOT EXISTS posts.tags (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(50) UNIQUE NOT NULL,
        slug VARCHAR(50) UNIQUE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS posts.post_tags (
        post_id UUID REFERENCES posts.posts(id) ON DELETE CASCADE,
        tag_id UUID REFERENCES posts.tags(id) ON DELETE CASCADE,
        PRIMARY KEY (post_id, tag_id)
    );
    
    -- Comment Service Tables
    CREATE TABLE IF NOT EXISTS comments.comments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id UUID NOT NULL,
        author_id UUID NOT NULL,
        parent_id UUID REFERENCES comments.comments(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        is_deleted BOOLEAN DEFAULT false,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        edited_at TIMESTAMP WITH TIME ZONE
    );
    
    CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments.comments(post_id);
    CREATE INDEX IF NOT EXISTS idx_comments_author_id ON comments.comments(author_id);
    CREATE INDEX IF NOT EXISTS idx_comments_parent_id ON comments.comments(parent_id);
    
    -- Like Service Tables
    CREATE TABLE IF NOT EXISTS likes.likes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        post_id UUID NOT NULL,
        user_id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(post_id, user_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_likes_post_id ON likes.likes(post_id);
    CREATE INDEX IF NOT EXISTS idx_likes_user_id ON likes.likes(user_id);
    
    -- Create indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_users_email ON auth.users(email);
    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON auth.refresh_tokens(token);
    CREATE INDEX IF NOT EXISTS idx_profiles_username ON users.profiles(username);
    CREATE INDEX IF NOT EXISTS idx_posts_author_id ON posts.posts(author_id);
    CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts.posts(slug);
    CREATE INDEX IF NOT EXISTS idx_posts_status ON posts.posts(status);
    CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts.posts(created_at);
    
    -- Insert some sample tags
    INSERT INTO posts.tags (name, slug) VALUES 
        ('Technology', 'technology'),
        ('Programming', 'programming'),
        ('Tutorial', 'tutorial'),
        ('News', 'news'),
        ('Opinion', 'opinion')
    ON CONFLICT (name) DO NOTHING;
    
EOSQL

echo "Database initialization completed!"
